# API reference

Patient endpoints require `Authorization: Bearer <access_token>`. Base path `/api/v1`.

Full request/response schemas: [openapi.json](openapi.json), or `/docs` on the running backend.

Errors use `{"error":{"code":422,"message":"Invalid input","fields":[...]}}`. Validation errors omit submitted values.

| Method | Path | Operation |
| --- | --- | --- |
| GET | `/health` | Health |
| GET | `/ready` | Ready |
| GET | `/api/v1/auth/recaptcha-config` | Configuration |
| GET | `/api/v1/auth/mobile-recaptcha` | Checkbox Page |
| POST | `/api/v1/auth/register` | Register |
| POST | `/api/v1/auth/otp/request` | Request Otp |
| POST | `/api/v1/auth/otp/verify` | Verify Otp |
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/auth/refresh` | Refresh |
| POST | `/api/v1/auth/logout` | Logout |
| POST | `/api/v1/auth/password` | Change Password |
| GET | `/api/v1/documents` | Documents |
| POST | `/api/v1/documents` | Upload |
| GET | `/api/v1/documents/{document_id}` | Status |
| DELETE | `/api/v1/documents/{document_id}` | Delete Document |
| GET | `/api/v1/documents/{document_id}/pages/{page_id}` | Page |
| POST | `/api/v1/documents/{document_id}/retry` | Retry |
| GET | `/api/v1/documents/{document_id}/analysis` | Analysis |
| PUT | `/api/v1/documents/{document_id}/analysis` | Edit Analysis |
| POST | `/api/v1/documents/{document_id}/confirm` | Confirm |
| GET | `/api/v1/treatments` | Treatments |
| GET | `/api/v1/treatments/{treatment_id}` | Treatment |
| PUT | `/api/v1/treatments/{treatment_id}/schedules` | Replace Schedules |
| POST | `/api/v1/treatments/{treatment_id}/complete` | Complete |
| GET | `/api/v1/doses` | Doses |
| POST | `/api/v1/doses/{dose_id}/events` | Track |
| GET | `/api/v1/doses/{dose_id}/events` | Dose History |
| GET | `/api/v1/notifications/preferences` | Preferences |
| PUT | `/api/v1/notifications/preferences` | Set Preferences |
| GET | `/api/v1/notifications/intent` | Intent |
| POST | `/api/v1/notifications/devices` | Register Device |
| DELETE | `/api/v1/notifications/devices/{device_id}` | Deregister Device |
| GET | `/api/v1/demo/providers` | Providers |
| GET | `/api/v1/demo/providers/{provider_id}` | Provider |
| GET | `/api/v1/demo/providers/{provider_id}/slots` | Slots |
| GET | `/api/v1/demo/bookings` | Bookings |
| POST | `/api/v1/demo/bookings` | Book |
| DELETE | `/api/v1/demo/bookings/{booking_id}` | Cancel |
| GET | `/api/v1/demo/inventory` | Inventory |
| GET | `/api/v1/demo/orders` | Orders |
| POST | `/api/v1/demo/orders` | Order |
| GET | `/api/v1/profile` | Profile |
| PUT | `/api/v1/profile` | Update Profile |
| GET | `/api/v1/dashboard` | Dashboard |
| GET | `/api/v1/chat` | Chat History |
| POST | `/api/v1/chat` | Chat |
| DELETE | `/api/v1/chat` | Clear Chat |
| GET | `/api/v1/speech/capabilities` | Speech Capabilities |
| DELETE | `/api/v1/account` | Delete Account |

## Workflow notes

Registration creates an unverified account and sends a verification OTP. OTP reset requires `new_password`. Refresh rotates both credentials; replay revokes the session family. Logout signs out all sessions.

Document upload is multipart: ordered repeated `files` parts, `document_type`, and `ai_consent=true`. One group is one document. The API returns immediately with status `queued`. Poll document details; the independent worker advances to `processing`, then `review` or `error`. Retry accepts failed documents only. Page access is private; `?preview=true` renders a PDF page to PNG in memory.

GET analysis returns `revision` and `extraction`. PUT the full corrected extraction with that revision. Confirmation requires the current revision and `confirmed=true`. Each schedule includes medicine index, explicit times/dates/timezone and `timing_confirmed=true`. Ambiguous instructions require recorded clinician verification; missing critical fields still block scheduling. Confirming without schedules saves a reviewed plan without reminders.

Schedule replacement uses treatment revision and cancels future old doses while retaining event history. Doses are generated in a bounded rolling window from activation time. Dose-event POST requires status, expected prior status and an idempotency key. Duplicate identical submissions are safe; corrections append a new event.

Notification intent is the server source of truth. Local delivery uses a seven-day / 48-alert device queue. Remote devices register native FCM tokens; local and remote preferences select alternative delivery paths.

Speech is device-native: `/speech/capabilities` describes the implementation; reviewed text is submitted to `/chat`. There is intentionally no fake server transcription/audio endpoint. Chat reads confirmed records only. History is opt-in through Profile and DELETE `/chat` clears it.

All `/demo` data and transactions are synthetic. Bookings reserve database-constrained slots. Cancellation frees the slot. Order prices are calculated server-side from synthetic inventory; clients cannot choose prices.
