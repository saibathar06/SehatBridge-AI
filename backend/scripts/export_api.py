import json
from pathlib import Path
from app.main import app

schema = app.openapi()
root = Path(__file__).resolve().parents[2] / 'docs'
(root / 'openapi.json').write_text(json.dumps(schema, indent=2), encoding='utf-8')
lines = [
    '# API reference', '',
    'Patient endpoints require `Authorization: Bearer <access_token>`. Base path `/api/v1`.', '',
    'Full request/response schemas: [openapi.json](openapi.json), or `/docs` on the running backend.', '',
    'Errors use `{"error":{"code":422,"message":"Invalid input","fields":[...]}}`. Validation errors omit submitted values.', '',
    '| Method | Path | Operation |', '| --- | --- | --- |',
]
for path, operations in schema['paths'].items():
    for method, operation in operations.items():
        if method in ('get', 'post', 'put', 'delete'):
            lines.append(f'| {method.upper()} | `{path}` | {operation.get("summary", "")} |')
lines += ['', '## Workflow notes', '',
    'Registration creates an unverified account and sends a verification OTP. OTP reset requires `new_password`. Refresh rotates both credentials; replay revokes the session family. Logout signs out all sessions.', '',
    'Document upload is multipart: ordered repeated `files` parts, `document_type`, and `ai_consent=true`. One group is one document. The API returns immediately with status `queued`. Poll document details; the independent worker advances to `processing`, then `review` or `error`. Retry accepts failed documents only. Page access is private; `?preview=true` renders a PDF page to PNG in memory.', '',
    'GET analysis returns `revision` and `extraction`. PUT the full corrected extraction with that revision. Confirmation requires the current revision and `confirmed=true`. Each schedule includes medicine index, explicit times/dates/timezone and `timing_confirmed=true`. Ambiguous instructions require recorded clinician verification; missing critical fields still block scheduling. Confirming without schedules saves a reviewed plan without reminders.', '',
    'Schedule replacement uses treatment revision and cancels future old doses while retaining event history. Doses are generated in a bounded rolling window from activation time. Dose-event POST requires status, expected prior status and an idempotency key. Duplicate identical submissions are safe; corrections append a new event.', '',
    'Notification intent is the server source of truth. Local delivery uses a seven-day / 48-alert device queue. Remote devices register native FCM tokens; local and remote preferences select alternative delivery paths.', '',
    'Speech is device-native: `/speech/capabilities` describes the implementation; reviewed text is submitted to `/chat`. There is intentionally no fake server transcription/audio endpoint. Chat reads confirmed records only. History is opt-in through Profile and DELETE `/chat` clears it.', '',
    'All `/demo` data and transactions are synthetic. Bookings reserve database-constrained slots. Cancellation frees the slot. Order prices are calculated server-side from synthetic inventory; clients cannot choose prices.',
]
(root / 'api.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(f'Exported {len(schema["paths"])} API paths')
