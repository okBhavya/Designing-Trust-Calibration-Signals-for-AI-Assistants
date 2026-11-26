# Smoke test

A manual end-to-end check before any pilot session and after every deployment. Tick each box; if
one fails, stop and record what you saw (screenshot, browser console, API log).

Commands are PowerShell. "Local" means the API at `http://127.0.0.1:8000` with SQLite
(`apps\api\calibrai.db`); "deployed" means the Render API and its PostgreSQL database
(see `docs/DEPLOY.md`).

## 0. Before you start

- [ ] The API is up: `Invoke-RestMethod <api>/health` returns `status: ok`.
- [ ] It uses the real engine: `CALIBRAI_SIGNAL_PROVIDER=selfconsistency` and `LLM_API_KEY` are set.
- [ ] The database is migrated: `python -m alembic current` (in `apps\api`) prints `0002_study_trials (head)`.
- [ ] For the harness: `CALIBRAI_STUDY_ENROLLMENT_CODE` and `CALIBRAI_STUDY_ORIGINS` are set.

Database queries below use this helper for the local SQLite database (run in `apps\api`). For
PostgreSQL, run the same SQL in `psql` and compare `participant_id` with the dashed UUID.

```powershell
function Invoke-Sql($sql) { python -c "import sqlite3,sys; [print(r) for r in sqlite3.connect('calibrai.db').execute(sys.argv[1])]" $sql }
# SQLite stores UUIDs as 32 hex characters without dashes:
$participantKey = '<participant id>'.Replace('-', '')
```

## A. Extension in API mode (ChatGPT, Claude, Gemini)

### Setup

- [ ] Build: local API, `npx wxt build --mode development` and load `.output\chrome-mv3-dev`;
      deployed API, build with `WXT_API_ORIGIN=<api>` and load `.output\chrome-mv3`.
- [ ] `chrome://extensions` > Developer mode > **Load unpacked**. CalibrAI shows no errors.
- [ ] Deployed only: `chrome-extension://<extension id>` is in `CALIBRAI_API_ORIGINS`.
- [ ] Create a participant and token (README, "Extension"; use the deployed URL and
      `CALIBRAI_ENROLLMENT_SECRET` for a deployed API) and record consent.
- [ ] Options page: mode **Authenticated API**, the API URL, the participant ID and the token.
      **Save signal settings**.
- [ ] Reload every open ChatGPT, Claude and Gemini tab (the extension only runs on pages loaded
      after it).

### On each site: ChatGPT, Claude, Gemini

Ask two questions in a new chat: one well known ("When was the Eiffel Tower completed?") and one
the model often gets wrong ("In what year did Gordon Plotkin win the ACM SIGPLAN Programming
Languages Achievement Award?").

| Check | ChatGPT | Claude | Gemini |
|---|---|---|---|
| When the answer finishes, a **Checking answer…** pill appears under it | [ ] | [ ] | [ ] |
| Within about 25 s it becomes a real level (Likely reliable, Partly consistent, Check before relying on it, or Not checkable), not "Couldn't check this answer" | [ ] | [ ] | [ ] |
| Exactly one pill per answer (no duplicates) | [ ] | [ ] | [ ] |
| Reload the page: earlier answers show their level again, with no error | [ ] | [ ] | [ ] |
| Click the pill: the details list the checked claims, weakest first, with one mark per sample; Escape closes them | [ ] | [ ] | [ ] |
| Dismiss (×) removes the pill | [ ] | [ ] | [ ] |
| Switch the site to dark mode: the pill switches too and stays readable | [ ] | [ ] | [ ] |
| The popup shows the site you are on | [ ] | [ ] | [ ] |

### In the database

- [ ] One stored signal per answer, per site:
      `Invoke-Sql "SELECT platform, model_version, COUNT(*) FROM live_signals WHERE participant_id = '$participantKey' GROUP BY platform, model_version"`
      shows `chatgpt`, `claude` and `gemini`, each with `selfconsistency-v2:…` and a count of 2.
- [ ] Events for each site:
      `Invoke-Sql "SELECT platform, event_type, COUNT(*) FROM signal_events WHERE participant_id = '$participantKey' GROUP BY platform, event_type"`
      shows `signal_shown`, `explanation_opened` and `signal_dismissed` for every platform.
- [ ] No raw text is stored unless `CALIBRAI_STORE_RAW_CONVERSATION` is on:
      `Invoke-Sql "SELECT COUNT(*) FROM live_signals WHERE prompt IS NOT NULL OR answer IS NOT NULL"` prints `(0,)`.

## B. Study harness

Run against the API (`npm run dev` in `apps\study`, or the deployed harness), with
`?code=<CALIBRAI_STUDY_ENROLLMENT_CODE>` in the URL. Use a new private window for each run: each
enrollment is a new participant. On an empty database the first three enrollments get one
condition each; you can tell them apart by what the trials show.

### Every condition

- [ ] Without `?code=` the consent page says the link is missing its access code and **Start** stays disabled.
- [ ] The consent page says the answers are pre-generated, data is pseudonymous, and you can stop at any time.
- [ ] **Start** is disabled until the box is ticked; then enrollment succeeds.
- [ ] Demographics: age band and AI experience (1–5) are required.
- [ ] 2 practice trials, then "Practice done", then "Question 1 of 30".
- [ ] **Next** is disabled until both Accept/Reject and a confidence level are chosen.
- [ ] The header shows **Saving…** briefly after each trial, then nothing.
- [ ] DevTools > Network > **Offline**, answer a trial: the header says "Saving… (connection
      problem, retrying)". Back **Online**: it clears, and that trial is stored once.
- [ ] After 30 trials, the 5 questionnaire items (1–7) are all required; the debrief says all
      answers are saved and explains the fixed 70% accuracy and that the checker can be wrong.
- [ ] At 375 px wide (DevTools device toolbar) nothing overflows and every control is usable.
- [ ] With dark mode on (OS setting, or DevTools > Rendering > `prefers-color-scheme: dark`) the
      page and the pill are dark and readable.
- [ ] Keyboard only: every control can be reached with Tab and used with Space or Enter.

### Per condition

| Check | baseline | A | C |
|---|---|---|---|
| The instructions mention the checker (A, C) or don't (baseline) | [ ] | [ ] | [ ] |
| No pill under answers (baseline) / a pill under every answer (A, C) | [ ] | [ ] | [ ] |
| The pill expands into the checked claims | n/a | [ ] | [ ] |
| Dotted underlines on flagged sentences (C only; not on every answer) | n/a | n/a | [ ] |
| Hover, tap or Tab onto an underline shows "Flagged by the checker" and the reason; Escape hides it | n/a | n/a | [ ] |

### Stop and delete

- [ ] In one more run, **Stop** > **Stop and delete my answers** says everything was deleted, and
      the participant is gone: `Invoke-Sql "SELECT COUNT(*) FROM participants WHERE id = '$participantKey'"` prints `(0,)`.

### Demo mode

- [ ] `npm run demo` (no API needed): the banner says "Demo: nothing is saved"; `?condition=C`
      shows underlines; the debrief says nothing was saved.

### Export

- [ ] `python apps\api\scripts\export_study.py` (add `--database-url <url>` for PostgreSQL) writes
      four CSV files to `apps\api\exports\<time>\`.
- [ ] `participants.csv` has only `participant_id`, `condition` and `consent_version`; the deleted
      participant is absent.
- [ ] `trials.csv` has 30 rows per completed participant, positions 0–29, no practice items, and
      `decision_ms` greater than 0.
- [ ] `events.csv` has `tooltip_opened` only for the condition C participant, and no events for
      the baseline participant.
- [ ] `questionnaires.csv` has `age_band`, `ai_experience` and `trust_1`…`trust_5` for each
      completed participant.
- [ ] Delete the test participants (or the test database) before inviting anyone. Exports stay
      out of the repository.
