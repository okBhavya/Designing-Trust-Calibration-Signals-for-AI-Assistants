from abc import ABC, abstractmethod
from time import perf_counter

from app.schemas.signal import SignalRequest, SignalResponse


class SignalProvider(ABC):
    @abstractmethod
    def evaluate(self, request: SignalRequest) -> SignalResponse:
        raise NotImplementedError


class MockSignalProvider(SignalProvider):
    def evaluate(self, request: SignalRequest) -> SignalResponse:
        started = perf_counter()
        if not request.answer:
            confidence, score = "low", 0.0
            explanation = "No answer text was provided for this mock signal."
        elif len(request.answer) > 700:
            confidence, score = "medium", 0.65
            explanation = "Long answers receive a medium mock signal pending real assessment."
        else:
            confidence, score = "high", 0.85
            explanation = "This deterministic mock signal is not a factuality assessment."
        return SignalResponse(
            confidence=confidence,
            score=score,
            explanation=explanation,
            modelVersion="mock-v1",
            processingLatencyMs=max(0, round((perf_counter() - started) * 1000)),
        )
