# Study harness (`apps/study`)

A static Vite + React page that runs the trust-calibration study: consent, demographics, 2 practice
trials, 30 main trials in random order, a 5-item trust questionnaire and a debrief.

- **Trials** come from `data/questions.json` (bundled at build time; 30 real answers, 21 correct).
  Practice items are two other real answers from the validation run (`src/practiceItems.json`).
- **Conditions** are assigned by the API on enrollment: `baseline` (no signal), `A` (the overlay pill)
  and `C` (the pill plus dotted underlines on flagged sentences, with a tooltip).
- **Shared code:** the overlay components and colour tokens are imported from `src/overlay` through the
  `@calibrai` alias, never copied. Sentence splitting is a port of the backend's, checked against
  `contracts/sentence_splits.json`.
- **Saving:** every record goes through an in-memory outbox that retries temporary failures; records the
  server rejects are shown and can be downloaded. Trial and questionnaire posts are idempotent.

## Run locally against the local API

```powershell
# API (terminal 1): migrate, then start with a study code and the harness origin
Set-Location apps\api
python -m alembic upgrade head
$env:CALIBRAI_STUDY_ENROLLMENT_CODE = 'local-study-code'
$env:CALIBRAI_STUDY_ORIGINS = 'http://localhost:5174'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Harness (terminal 2)
Set-Location apps\study
npm run dev
# open http://localhost:5174/?code=local-study-code
```

`npm run demo` runs the whole flow with no backend (nothing is saved); add `?condition=A`, `C` or
`baseline` to the URL to pick a condition. Settings are in `.env.example`.

## Checks

```powershell
npm test          # vitest
npm run build     # tsc + vite build -> dist/
```

The trust questionnaire wording in `src/screens.tsx` is a placeholder until the study protocol fixes
the validated instrument.
