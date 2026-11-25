import asyncio
import json
import logging
from uuid import uuid4

import pytest

from app.config import Settings, get_settings
from app.schemas.signal import SignalRequest
from app.services.llm_client import LLMResult, LLMUnavailableError
from app.services.selfconsistency_service import (
    EXTRACT_SYSTEM,
    JUDGE_SYSTEM,
    SAMPLE_SYSTEM,
    ClaimConsistency,
    SelfConsistencyProvider,
    agreement_reason,
    short_claim,
    state_for,
    ungrounded_terms,
    weakest_claim,
)

ANSWER = (
    "The Eiffel Tower is in Paris. It was completed in 1889 for the World's Fair. "
    "It is about 330 metres tall."
)


class FakeLLMClient:
    """Scripted LLMClient: routes by system prompt, records calls, never touches the network."""

    model = "fake-model"

    def __init__(self, extraction=None, judge=None, samples=None, sample_delay=0.01, fail_samples=False):
        self.extraction = list(extraction or [])
        self.judge = list(judge or [])
        self.samples = samples or [f"Sample answer {i}" for i in range(1, 6)]
        self.sample_delay = sample_delay
        self.fail_samples = fail_samples
        self.calls: list[str] = []
        self.models: list[str | None] = []
        self.temperatures: list[float | None] = []
        self.in_flight = 0
        self.max_in_flight = 0
        self.closed = False
        self._sample_index = 0

    async def complete(self, *, system, prompt, json_schema=None, temperature=None, model=None):
        if system.startswith(EXTRACT_SYSTEM):
            self.calls.append("extract" if system == EXTRACT_SYSTEM else "extract_strict")
            self.models.append(model)
            return LLMResult(self.extraction.pop(0), 100, 50)
        if system == JUDGE_SYSTEM:
            self.calls.append("judge")
            return LLMResult(self.judge.pop(0), 300, 80)
        assert system == SAMPLE_SYSTEM and json_schema is None
        self.calls.append("sample")
        self.temperatures.append(temperature)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(self.sample_delay)
            if self.fail_samples:
                raise LLMUnavailableError("APIConnectionError")
            text = self.samples[self._sample_index % len(self.samples)]
            self._sample_index += 1
            return LLMResult(text, 20, 40)
        finally:
            self.in_flight -= 1

    async def aclose(self):
        self.closed = True


def extraction_json(claims, answer_type="factual"):
    return json.dumps({"answer_type": answer_type, "claims": claims})


def judge_json(rows):
    return json.dumps({"claims": [{"claim_index": i, "verdicts": row} for i, row in enumerate(rows)]})


CLAIMS = [
    {"claim": "The Eiffel Tower is in Paris.", "sentence_indices": [0], "materiality": "high"},
    {"claim": "The Eiffel Tower was completed in 1889.", "sentence_indices": [1], "materiality": "high"},
    {"claim": "The Eiffel Tower is about 330 metres tall.", "sentence_indices": [2], "materiality": "low"},
]
S, C, N = "supported", "contradicted", "not_mentioned"


def request(answer=ANSWER, prompt="Tell me about the Eiffel Tower."):
    return SignalRequest(
        participant_id=uuid4(), platform="chatgpt", answer_hash="e" * 64, prompt=prompt, answer=answer
    )


def provider_for(client, **overrides):
    settings = Settings(**overrides)
    return SelfConsistencyProvider(client_factory=lambda: client, settings=settings)


def consistency(materiality, supported, contradicted=0, samples=5, text="claim"):
    verdicts = tuple([S] * supported + [C] * contradicted + [N] * (samples - supported - contradicted))
    return ClaimConsistency(f"clm_{text}", text, (0,), materiality, verdicts)


# --- scoring and aggregation -----------------------------------------------------------------


def test_support_counts_only_samples_that_mention_the_claim():
    claim = consistency("high", 2, contradicted=1)  # 2 supported, 1 contradicted, 2 not mentioned
    assert (claim.mentions, claim.addressed) == (3, True)
    assert claim.support_rate == pytest.approx(2 / 3)


@pytest.mark.parametrize("supported,contradicted", [(0, 0), (1, 0), (0, 1)])
def test_claims_mentioned_by_fewer_than_two_samples_are_not_addressed(supported, contradicted):
    assert not consistency("high", supported, contradicted).addressed


def test_weakest_addressed_high_claim_sets_the_score_even_if_a_low_claim_is_weaker():
    claims = [
        consistency("high", 4, 1, text="a"),
        consistency("high", 3, 2, text="b"),
        consistency("low", 0, 5, text="c"),
        consistency("high", 0, 0, text="unaddressed"),  # never mentioned: must not become the weakest
    ]
    assert weakest_claim(claims).text == "b"
    assert weakest_claim(claims).support_rate == pytest.approx(0.6)


def test_weakest_claim_falls_back_to_addressed_claims_of_any_materiality():
    claims = [consistency("high", 1, text="lone"), consistency("medium", 5, text="a"), consistency("low", 2, 2, text="b")]
    assert weakest_claim(claims).text == "b"


def test_no_addressed_claim_has_no_weakest():
    assert weakest_claim([consistency("high", 1), consistency("low", 0, 1)]) is None


@pytest.mark.parametrize(
    "score,expected", [(1.0, "high"), (0.8, "high"), (0.79, "medium"), (0.6, "medium"), (0.59, "low"), (0.0, "low")]
)
def test_state_uses_the_080_and_060_thresholds(score, expected):
    assert state_for(score, 0.8, 0.6) == expected


def test_thresholds_are_configurable():
    assert state_for(0.6, 0.9, 0.7) == "low"
    with pytest.raises(ValueError):
        Settings(selfconsistency_high_threshold=0.5, selfconsistency_medium_threshold=0.7)


def test_reason_strings_count_unchecked_details():
    assert agreement_reason(consistency("high", 4, 1), '"x"', 2) == '4 of 5 attempts agreed on "x"; 2 side details not checked.'
    assert agreement_reason(consistency("high", 5), '"x"') == 'All 5 attempts agreed on "x".'
    assert agreement_reason(consistency("high", 2, 1), '"x"', 1) == (
        '2 of 3 attempts that mentioned it agreed on "x"; 1 side detail not checked.'
    )
    long_text = "The Eiffel Tower was completed in 1889 for the Exposition Universelle in Paris, France."
    assert short_claim(long_text).endswith("…")
    assert len(short_claim(long_text)) <= 61


# --- full pipeline --------------------------------------------------------------------------


def test_pipeline_scores_addressed_claims_and_fills_the_contract():
    client = FakeLLMClient(
        extraction=[extraction_json(CLAIMS)],
        # claim 0: 5/5; claim 1: 1 supported, 3 contradicted (1/4); claim 2: mentioned once -> not addressed
        judge=[judge_json([[S, S, S, S, S], [S, C, C, C, N], [S, N, N, N, N]])],
    )
    response = provider_for(client).evaluate(request())

    assert client.calls.count("sample") == 5
    assert client.max_in_flight == 5, "samples must run in parallel"
    assert client.temperatures == [0.7] * 5
    assert client.calls.count("extract") == 1 and client.calls.count("judge") == 1
    assert client.closed

    assert response.score == pytest.approx(0.25)
    assert response.assessment_state == "low"
    assert response.confidence == "low"
    assert response.explanation == (
        '1 of 4 attempts that mentioned it agreed on "The Eiffel Tower was completed in 1889"; '
        "1 side detail not checked."
    )
    assert response.model_version == "selfconsistency-v2:fake-model"
    assert "Eiffel" not in response.stored_explanation
    assert response.stored_explanation.startswith("1 of 4 attempts that mentioned it agreed on claim clm_")

    assessments = {item.claim: item for item in response.claim_assessments}
    assert assessments["The Eiffel Tower is in Paris."].assessment == "consistent"
    completed = assessments["The Eiffel Tower was completed in 1889."]
    assert completed.assessment == "inconsistent"
    assert completed.evidence_strength == "1 of 4 mentions supported (5 samples)"
    assert completed.supporting_source_ids == ["sample-1"]
    assert completed.contradicting_source_ids == ["sample-2", "sample-3", "sample-4"]
    height = assessments["The Eiffel Tower is about 330 metres tall."]
    assert height.assessment == "not_addressed"
    assert height.uncertainty is None

    # Only the addressed, contradicted claim is flagged; the unmentioned side detail is not.
    assert [flag.sentence_index for flag in response.sentence_flags] == [1]
    assert response.sentence_flags[0].claim_ids == [completed.claim_id]
    assert response.sentence_flags[0].label == "low_agreement"


def test_side_details_that_samples_omit_do_not_lower_the_score_or_get_flagged():
    client = FakeLLMClient(
        extraction=[extraction_json(CLAIMS)],
        judge=[judge_json([[S] * 5, [S] * 5, [N] * 5])],
    )
    response = provider_for(client).evaluate(request())
    assert (response.assessment_state, response.score) == ("high", 1.0)
    assert response.sentence_flags == []
    assert response.explanation.endswith("; 1 side detail not checked.")


def test_no_addressed_claims_is_insufficient_evidence():
    client = FakeLLMClient(
        extraction=[extraction_json(CLAIMS)],
        judge=[judge_json([[S, N, N, N, N], [N] * 5, [C, N, N, N, N]])],
    )
    response = provider_for(client).evaluate(request())
    assert response.assessment_state == "insufficient_evidence"
    assert response.score is None and response.confidence is None
    assert response.sentence_flags == []
    assert {item.assessment for item in response.claim_assessments} == {"not_addressed"}
    assert "none could be checked" in response.explanation


def test_supported_but_contradicted_claims_above_threshold_are_not_flagged():
    client = FakeLLMClient(
        extraction=[extraction_json(CLAIMS[1:2])],
        judge=[judge_json([[S, S, S, C, N]])],  # 3 of 4 = 0.75 -> medium, not flagged
    )
    response = provider_for(client).evaluate(request())
    assert response.assessment_state == "medium"
    assert response.score == pytest.approx(0.75)
    assert response.sentence_flags == []


def test_high_state_when_every_attempt_agrees():
    client = FakeLLMClient(extraction=[extraction_json(CLAIMS[:1])], judge=[judge_json([[S] * 5])])
    response = provider_for(client).evaluate(request())
    assert (response.assessment_state, response.score) == ("high", 1.0)
    assert response.sentence_flags == []
    assert response.explanation == 'All 5 attempts agreed on "The Eiffel Tower is in Paris".'


def test_claims_are_capped_at_eight():
    claims = [
        {"claim": f"The Eiffel Tower is in Paris, part {letter}.", "sentence_indices": [0], "materiality": "medium"}
        for letter in "abcdefghij"
    ]
    client = FakeLLMClient(extraction=[extraction_json(claims)], judge=[judge_json([[S] * 5] * 8)])
    response = provider_for(client).evaluate(request())
    assert len(response.claim_assessments) == 8


# --- strict JSON: retry once, then unavailable -------------------------------------------------


def test_malformed_extraction_is_retried_once_then_succeeds():
    client = FakeLLMClient(extraction=["not json", extraction_json(CLAIMS[:1])], judge=[judge_json([[S] * 5])])
    response = provider_for(client).evaluate(request())
    assert client.calls.count("extract") == 2
    assert response.assessment_state == "high"


@pytest.mark.parametrize(
    "bad_extraction",
    [
        "{not json",
        json.dumps({"answer_type": "factual", "claims": [{"claim": "x", "sentence_indices": [0]}]}),
        extraction_json([{"claim": "x", "sentence_indices": [99], "materiality": "high"}]),
    ],
)
def test_extraction_failing_twice_is_unavailable(bad_extraction):
    client = FakeLLMClient(extraction=[bad_extraction, bad_extraction])
    response = provider_for(client).evaluate(request())
    assert client.calls.count("extract") == 2
    assert response.assessment_state == "unavailable"
    assert response.score is None and response.confidence is None
    assert "judge" not in client.calls


def test_judge_matrix_with_wrong_shape_twice_is_unavailable():
    wrong = judge_json([[S, S, S]])  # three verdicts instead of five
    client = FakeLLMClient(extraction=[extraction_json(CLAIMS[:1])], judge=[wrong, wrong])
    response = provider_for(client).evaluate(request())
    assert client.calls.count("judge") == 2
    assert response.assessment_state == "unavailable" and response.score is None


def test_llm_failure_and_timeout_are_unavailable():
    failing = FakeLLMClient(extraction=[extraction_json(CLAIMS)], fail_samples=True)
    assert provider_for(failing).evaluate(request()).assessment_state == "unavailable"
    assert failing.closed

    slow = FakeLLMClient(extraction=[extraction_json(CLAIMS)], sample_delay=5)
    response = provider_for(slow, selfconsistency_timeout_seconds=0.05).evaluate(request())
    assert response.assessment_state == "unavailable" and response.score is None
    assert "timed out" in response.explanation


def test_missing_llm_key_is_unavailable_without_calls():
    settings = Settings()
    settings.llm_api_key = None
    response = SelfConsistencyProvider(settings=settings).evaluate(request())
    assert response.assessment_state == "unavailable"


# --- skip rules -----------------------------------------------------------------------------


def test_code_only_answer_abstains_without_llm_calls():
    client = FakeLLMClient()
    response = provider_for(client).evaluate(request(answer="```python\nprint('hi')\n```"))
    assert response.assessment_state == "abstained"
    assert response.score is None
    assert client.calls == []


@pytest.mark.parametrize("answer_type", ["creative", "small_talk", "code_only"])
def test_non_factual_answers_abstain_and_skip_the_judge(answer_type):
    client = FakeLLMClient(extraction=[extraction_json([], answer_type=answer_type)], sample_delay=5)
    response = provider_for(client).evaluate(request(answer="Hello there! Nice to meet you."))
    assert response.assessment_state == "abstained"
    assert response.score is None and response.confidence is None
    assert "judge" not in client.calls
    assert client.closed


def test_factual_answer_without_claims_abstains():
    client = FakeLLMClient(extraction=[extraction_json([])], sample_delay=5)
    response = provider_for(client).evaluate(request())
    assert response.assessment_state == "abstained" and response.score is None


def test_missing_answer_or_prompt_is_unavailable_without_calls():
    client = FakeLLMClient()
    assert provider_for(client).evaluate(request(answer=None)).assessment_state == "unavailable"
    assert provider_for(client).evaluate(request(prompt=None)).assessment_state == "unavailable"
    assert client.calls == []


# --- logging and privacy ----------------------------------------------------------------------


def test_logs_latency_and_token_usage_without_conversation_text(caplog):
    client = FakeLLMClient(extraction=[extraction_json(CLAIMS[:1])], judge=[judge_json([[S] * 5])])
    with caplog.at_level(logging.INFO, logger="calibrai.selfconsistency"):
        provider_for(client).evaluate(request())
    record = caplog.text
    assert "latency_ms=" in record
    assert "llm_calls=7" in record
    assert "input_tokens=500" in record  # 100 extract + 5 x 20 samples + 300 judge
    assert "output_tokens=330" in record
    assert "Eiffel" not in record


def test_api_returns_claims_but_stores_no_claim_text(client, auth_headers, monkeypatch):
    from app.api.routes import signal as signal_route
    from app.database.connection import get_db
    from app.database.models import LiveSignal

    fake = FakeLLMClient(
        extraction=[extraction_json(CLAIMS)],
        judge=[judge_json([[S] * 5, [S, S, C, C, C], [S] * 5])],
    )
    monkeypatch.setattr(signal_route, "get_provider", lambda: SelfConsistencyProvider(client_factory=lambda: fake))
    participant_id = uuid4()
    headers = auth_headers(participant_id)
    client.post(
        "/v1/consent",
        json={"participant_id": str(participant_id), "consent_version": "test-consent", "status": "granted"},
        headers=headers,
    )
    response = client.post(
        "/v1/signal",
        json={
            "participant_id": str(participant_id),
            "platform": "claude",
            "answer_hash": "f" * 64,
            "prompt": "Tell me about the Eiffel Tower.",
            "answer": ANSWER,
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["assessmentState"] == "low"
    assert "Eiffel" in body["explanation"]
    assert "stored_explanation" not in body and "storedExplanation" not in body
    assert body["claimAssessments"][1]["claim"] == "The Eiffel Tower was completed in 1889."

    db = next(client.app.dependency_overrides[get_db]())
    try:
        stored = db.query(LiveSignal).filter_by(participant_id=participant_id).one()
        assert "eiffel" not in json.dumps(stored.response_json).lower()
        assert stored.response_json["explanation"].startswith("2 of 5 attempts agreed on claim clm_")
        assert stored.model_version == "selfconsistency-v2:fake-model"
    finally:
        db.close()


# --- configuration ---------------------------------------------------------------------------


def test_selfconsistency_is_allowed_in_production_with_a_key(monkeypatch):
    from pydantic import SecretStr

    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "session_signing_secret", "secure-session-secret")
    monkeypatch.setattr(settings, "enrollment_secret", "secure-enrollment-secret")
    monkeypatch.setattr(settings, "signal_provider", "selfconsistency")
    monkeypatch.setattr(settings, "llm_api_key", None)
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        settings.validate_deployment_security()
    monkeypatch.setattr(settings, "llm_api_key", SecretStr("server-side-key"))
    settings.validate_deployment_security()


def test_llm_key_is_read_from_llm_api_key(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "from-env")
    assert Settings().llm_api_key.get_secret_value() == "from-env"
    assert "from-env" not in repr(Settings())


# --- Anthropic client adapter (no network: the SDK call is replaced) ---------------------------


def test_anthropic_client_sends_schema_never_temperature_and_maps_failures():
    from types import SimpleNamespace

    import anthropic
    import httpx

    from app.services.llm_client import AnthropicLLMClient

    llm = AnthropicLLMClient(api_key="test-key", model="claude-opus-5-5", timeout_seconds=20)
    sent = {}

    def reply(stop_reason="end_turn"):
        async def create(**kwargs):
            sent.update(kwargs)
            return SimpleNamespace(
                stop_reason=stop_reason,
                content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text='{"a": 1}')],
                usage=SimpleNamespace(input_tokens=11, output_tokens=7),
            )
        return create

    llm._client.messages.create = reply()
    result = asyncio.run(llm.complete(system="s", prompt="p", json_schema={"type": "object"}, temperature=0.7))
    assert (result.text, result.input_tokens, result.output_tokens) == ('{"a": 1}', 11, 7)
    assert "temperature" not in sent
    assert sent["model"] == "claude-opus-5-5"
    assert sent["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": {"type": "object"}}}

    llm._client.messages.create = reply("refusal")
    with pytest.raises(LLMUnavailableError, match="refusal"):
        asyncio.run(llm.complete(system="s", prompt="p"))

    async def timeout(**kwargs):
        raise anthropic.APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))

    llm._client.messages.create = timeout
    with pytest.raises(LLMUnavailableError, match="APITimeoutError"):
        asyncio.run(llm.complete(system="s", prompt="p"))


def test_default_llm_model_is_haiku():
    assert Settings().llm_model == "claude-haiku-5-5"


# --- claim grounding (no LLM call) ------------------------------------------------------------

WRONG_ANSWER = "It was completed in 1902 for the Paris World Fair."
WRONG_PROMPT = "When was the Eiffel Tower completed?"


def test_grounding_flags_numbers_the_sentence_does_not_state():
    # The 1902 case: Haiku "corrected" the answer's year while extracting.
    claim = "The Eiffel Tower was built for the 1889 Paris World Fair."
    assert ungrounded_terms(claim, WRONG_ANSWER, WRONG_PROMPT, WRONG_ANSWER) == ["1889"]
    assert ungrounded_terms("The Eiffel Tower was completed in 1902.", WRONG_ANSWER, WRONG_PROMPT, WRONG_ANSWER) == []


def test_grounding_rules_for_numbers_and_names():
    answer = "The tower was designed by Gustave Eiffel's firm. It stands 1,063 feet tall."
    second = "It stands 1,063 feet tall."
    assert ungrounded_terms("The tower stands 1063 feet tall.", second, "How tall?", answer) == []
    # Names may come from elsewhere in the answer (resolving "it"); numbers may not.
    assert ungrounded_terms("Eiffel's tower stands 1063 feet tall.", second, "How tall?", answer) == []
    assert ungrounded_terms("It was designed in 1887.", "It was designed by Gustave Eiffel's firm.", "q", answer) == ["1887"]
    assert ungrounded_terms("It was designed by Stephen Sauvestre.", "It was designed by Gustave Eiffel's firm.", "q", answer) == [
        "Stephen",
        "Sauvestre",
    ]


def test_ungrounded_claim_is_retried_then_replaced_by_its_sentence():
    ungrounded = [
        {"claim": "The Eiffel Tower was completed in 1902.", "sentence_indices": [0], "materiality": "high"},
        {"claim": "The Eiffel Tower was built for the 1889 Paris World Fair.", "sentence_indices": [0], "materiality": "medium"},
    ]
    client = FakeLLMClient(
        extraction=[extraction_json(ungrounded), extraction_json(ungrounded)],  # the strict retry repeats it
        judge=[judge_json([[C] * 5, [C, C, C, N, N]])],
    )
    response = provider_for(client).evaluate(request(answer=WRONG_ANSWER, prompt=WRONG_PROMPT))

    assert (client.calls.count("extract"), client.calls.count("extract_strict")) == (1, 1)
    claims = [item.claim for item in response.claim_assessments]
    assert claims == ["The Eiffel Tower was completed in 1902.", WRONG_ANSWER]
    assert not any("1889" in claim for claim in claims)
    assert response.assessment_state == "low"


def test_strict_retry_replaces_an_ungrounded_extraction():
    first = [{"claim": "The Eiffel Tower was built for the 1889 Paris World Fair.", "sentence_indices": [0], "materiality": "high"}]
    fixed = [{"claim": "The Eiffel Tower was completed in 1902 for the Paris World Fair.", "sentence_indices": [0], "materiality": "high"}]
    client = FakeLLMClient(extraction=[extraction_json(first), extraction_json(fixed)], judge=[judge_json([[C] * 5])])
    response = provider_for(client).evaluate(request(answer=WRONG_ANSWER, prompt=WRONG_PROMPT))
    assert client.calls.count("extract_strict") == 1
    assert [item.claim for item in response.claim_assessments] == [fixed[0]["claim"]]


def test_grounded_extraction_is_not_retried(caplog):
    client = FakeLLMClient(extraction=[extraction_json(CLAIMS)], judge=[judge_json([[S] * 5] * 3)])
    with caplog.at_level(logging.INFO, logger="calibrai.selfconsistency"):
        provider_for(client).evaluate(request())
    assert "extract_strict" not in client.calls
    assert "grounding_retries=0 grounding_fallbacks=0" in caplog.text


def test_extraction_can_use_its_own_model():
    client = FakeLLMClient(extraction=[extraction_json(CLAIMS[:1])], judge=[judge_json([[S] * 5])])
    response = provider_for(client, llm_extraction_model="claude-sonnet-5-5").evaluate(request())
    assert client.models == ["claude-sonnet-5-5"]
    assert response.model_version == "selfconsistency-v2:fake-model+extract:claude-sonnet-5-5"

    default = FakeLLMClient(extraction=[extraction_json(CLAIMS[:1])], judge=[judge_json([[S] * 5])])
    assert provider_for(default).evaluate(request()).model_version == "selfconsistency-v2:fake-model"
    assert default.models == [None]


def test_extraction_model_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("CALIBRAI_LLM_EXTRACTION_MODEL", "claude-sonnet-5-5")
    assert Settings().llm_extraction_model == "claude-sonnet-5-5"
    monkeypatch.setenv("CALIBRAI_LLM_EXTRACTION_MODEL", "")
    assert Settings().llm_extraction_model is None


# --- refusals ---------------------------------------------------------------------------------

# Real Haiku answer from the validation run (simpleqa-3610): a refusal that scored High under v1.
KENTRIDGE_PROMPT = "What is the name of the 10-meter sculpture that William Kentridge created in 2009?"
KENTRIDGE_REFUSAL = (
    "I'm not certain of the name of a 10-meter sculpture William Kentridge made in 2009, and I don't want "
    "to guess and give you a wrong title. If you can tell me where you encountered it, such as a museum, "
    "public installation, or exhibition, I can help you narrow it down. Kentridge's official website or a "
    "museum collection record would also list his 2009 works reliably."
)
# Real answer (simpleqa-941): hedged, but it commits to a name, so it is not a refusal.
HEDGED_COMMIT = (
    "I'm not certain of this. I believe Dr. Mariell Jessup may have been among the early women to chair the "
    "American Heart Association's Board of Directors, but I can't confirm she was the first, so please verify "
    "with the AHA's official records or leadership history."
)


def test_refusal_answer_abstains_without_any_llm_call():
    client = FakeLLMClient()
    response = provider_for(client).evaluate(request(answer=KENTRIDGE_REFUSAL, prompt=KENTRIDGE_PROMPT))
    assert response.assessment_state == "abstained"
    assert response.score is None and response.confidence is None
    assert response.explanation == "The assistant didn't give a checkable answer."
    assert response.claim_assessments == [] and response.sentence_flags == []
    assert client.calls == []


def test_curly_apostrophes_are_still_recognised():
    client = FakeLLMClient()
    curly = KENTRIDGE_REFUSAL.replace("'", "’")
    assert provider_for(client).evaluate(request(answer=curly, prompt=KENTRIDGE_PROMPT)).assessment_state == "abstained"


def test_answer_with_one_hedge_sentence_is_still_scored():
    hedged = ANSWER + " I'm not sure about the exact height, though."
    client = FakeLLMClient(extraction=[extraction_json(CLAIMS)], judge=[judge_json([[S] * 5] * 3)])
    response = provider_for(client).evaluate(request(answer=hedged))
    assert client.calls.count("extract") == 1
    assert response.assessment_state == "high" and response.score == 1.0


def test_hedged_answer_that_commits_is_left_to_the_extraction():
    from app.services.reliability_service import normalize_answer
    from app.services.selfconsistency_service import looks_like_refusal

    question = "What is the first and last name of the first woman to chair the American Heart Association Board of Directors?"
    assert looks_like_refusal(normalize_answer(KENTRIDGE_REFUSAL), KENTRIDGE_PROMPT)
    assert not looks_like_refusal(normalize_answer(HEDGED_COMMIT), question)  # it names Mariell Jessup
    assert not looks_like_refusal(normalize_answer(ANSWER), "Tell me about the Eiffel Tower.")


def test_extraction_refusal_flag_abstains_and_skips_the_judge():
    vague = "Honestly, that one is hard to pin down. Records from that period disagree with each other."
    refusal = json.dumps({"answer_type": "factual", "refusal": True, "claims": []})
    client = FakeLLMClient(extraction=[refusal], sample_delay=5)
    response = provider_for(client).evaluate(request(answer=vague))
    assert response.assessment_state == "abstained" and response.score is None
    assert response.explanation == "The assistant didn't give a checkable answer."
    assert "judge" not in client.calls and client.closed


def test_extraction_prompt_asks_for_the_refusal_flag_and_no_self_claims():
    from app.services.selfconsistency_service import EXTRACTION_SCHEMA

    assert "refusal" in EXTRACTION_SCHEMA["required"]
    assert EXTRACTION_SCHEMA["properties"]["refusal"] == {"type": "boolean"}
    assert "Never extract claims about the assistant itself" in EXTRACT_SYSTEM
