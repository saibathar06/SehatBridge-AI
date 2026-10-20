# SehatBridge AI

A mobile-only Expo application with an independently deployable FastAPI backend. The core workflow is **upload → extract → review → confirm → schedule → track → ask**. The twelve supplied PNG references are preserved under `references/`.

For this prepared Windows workspace, start with the [local running guide](docs/local-running.md), which includes one-command PowerShell launch scripts.

Google reCAPTCHA v2 checkbox setup for authentication is documented in [reCAPTCHA configuration](docs/recaptcha.md). Enable it with your own backend-only key configuration; existing `.env` files are preserved.

## Run the backend

Python 3.14 is used by the tested development environment. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
.\.venv\Scripts\python.exe backend/scripts/init_env.py
cd backend
..\.venv\Scripts\alembic.exe upgrade head
..\.venv\Scripts\python.exe -m scripts.seed_demo
..\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --no-access-log
```

Run the processing/reminder worker in a second terminal, with `backend/` as its working directory:

```powershell
..\.venv\Scripts\python.exe -m app.worker
```

Set `GEMINI_API_KEY` and `GEMINI_MODEL` in `backend/.env` before processing documents. `gemini-3.5-flash` is a documented multimodal, structured-output capable option; verify access in your Google AI project. The model is configurable and there is no fabricated extraction fallback. See [AI architecture](docs/architecture.md).

SQLite is available for local smoke tests. PostgreSQL is required for production and concurrency guarantees. `compose.yaml` provisions PostgreSQL 18, Redis 8, migration, API and worker services. Set a strong `POSTGRES_PASSWORD` in the shell, configure `backend/.env`, and run `docker compose up --build`. Docker is not installed in the current development environment, so this stack still needs execution in a Docker host.

## Run the mobile app

```powershell
cd mobile
npm ci
Copy-Item .env.example .env
npx expo start --dev-client
```

Use a development build, not Expo Go. Native speech recognition and Android remote notifications need compiled native modules. First create and install the build using [Android build instructions](docs/android.md).

Configure `EXPO_PUBLIC_API_URL` before starting Metro or building:

| Target | API URL |
| --- | --- |
| Android emulator | `http://10.0.2.2:8000/api/v1` |
| Physical phone, same LAN | `http://YOUR_COMPUTER_LAN_IP:8000/api/v1` |
| Hosted / release build | `https://YOUR_BACKEND_HOST/api/v1` |

A phone's `localhost` points to the phone. Release builds enforce HTTPS. Never put Gemini, encryption, JWT or Firebase service-account secrets in the mobile environment.

## Development verification

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
cd ../mobile
npm run typecheck
npm test
npx expo install --check
npx expo export --platform android
```

Tests use synthetic users and documents, with an explicitly injected AI test double. They do not measure real Gemini accuracy. To run the real provider evaluation with the configured API key:

```powershell
cd backend
..\.venv\Scripts\python.exe -m scripts.generate_evaluation_set
..\.venv\Scripts\python.exe -m scripts.evaluate_extraction
```

The evaluation compares independently specified ground-truth fields, not model confidence. Synthetic pen strokes are an illegibility hard negative; authorized real handwritten prescriptions and an independently annotated held-out set are still needed for clinical handwriting evaluation.

## Demonstrate the complete journey

1. Register, read the privacy explanation and verify your email. Development-only OTPs appear in the backend terminal; production requires SMTP.
2. Set your name, language and timezone in Profile.
3. Upload one document group; reorder, rotate, remove or add photos before submission. Upload separate documents separately. PDF page order is retained.
4. Keep the worker running. Open Documents to see queued, processing, review or recoverable error status.
5. Review summary, medicines, tests, follow-ups and care instructions. Compare uncertainty flags with private source-page previews.
6. Correct critical fields. For unclear instructions, record clinician/pharmacist verification before enabling reminders.
7. Enter explicitly confirmed dates, times and timezone. No missing dose, timing, duration or date is auto-filled. Confirm the plan.
8. Enable local reminders in settings; schedule the 10-second test. Open the app regularly to replenish its bounded rolling queue.
9. Mark an actual dose taken/skipped and inspect correction history.
10. On a physical Android build, choose Hindi, tap the microphone and ask: “मुझे आज कौन-कौन सी दवाई लेनी है और मेरा नेक्स्ट टेस्ट कब होगा?” Review the transcript and send it. Hear a record-grounded answer.
11. Ask “डॉक्टर ने मेरी रिपोर्ट में क्या बताया?” to exercise Gemini explanations. A safety question returns an explicit verified-drug-source limitation until a reviewed reference provider is connected.
12. Explore synthetic appointment/lab slots and the pharmacy cart. All transactions are explicitly simulated and stored by the backend.

See [verification and limitations](docs/verification.md), [API](docs/api.md), [security](docs/security.md), [Firebase](docs/firebase.md), and [deployment](docs/deployment.md). This repository is an implemented MVP, not a claim of completed device, clinical or production validation.
