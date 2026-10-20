# Backend deployment

Provision PostgreSQL 18 and Redis 8 on a private network. Use database credentials with least privilege, TLS to managed services and private encrypted volumes. Build `backend/Dockerfile`, run `alembic upgrade head` as a release job, then deploy the API and worker separately. Migration must succeed before serving traffic. `compose.yaml` is a local deployment starting point; put it behind an HTTPS ingress before allowing patient use.

Generate configuration using `backend/scripts/init_env.py` only for development. Production secret generation belongs in a managed secret store. Configure:

- `ENVIRONMENT=production`, PostgreSQL `DATABASE_URL`, authenticated private `REDIS_URL`.
- Independent strong `JWT_SECRET`, `OTP_SECRET`, and base64-encoded 32-byte `ENCRYPTION_KEY`.
- `OTP_PROVIDER=smtp`, SMTP host, port, username, password and sender.
- `GEMINI_API_KEY`, a verified available multimodal `GEMINI_MODEL`, bounded timeout/output tokens and page batch size.
- `STORAGE_PATH` on a shared private encrypted volume accessible only to API/worker identities.
- Optional mounted `FIREBASE_CREDENTIALS`; never expose this through a frontend variable.
- Empty or explicit `CORS_ORIGINS`, upload/page limits, rate limits and warning-level logging.

The example's console OTP and SQLite are rejected in production. The worker requires the same database/storage/encryption settings as the API. PostgreSQL `FOR UPDATE SKIP LOCKED` supports competing extraction workers; current FCM dispatch should use one worker replica per deployment until delivery claiming is extended for multi-sender concurrency. Container restart policies recover worker failures. Add worker heartbeats and alerting before production; `/ready` currently checks database/Redis availability, not worker freshness or AI quota.

Set ingress request body limit to 21 MB or lower, body/header timeouts, request duration limits, connection limits and appropriate rate protections. The application bounds chunked/multipart body bytes and uploaded content, but ingress limits are also necessary. Enforce TLS; do not trust arbitrary proxy-forwarded client IP headers. If using a proxy, configure an explicit trusted proxy list in Uvicorn and verify rate limits use the intended client identity.

Disable request-body and credential logging everywhere. Uvicorn commands use `--no-access-log`. Collect only error categories, latency, queue depth, model quota usage, worker heartbeat and notification delivery counts. Alert on queued jobs stuck beyond their leases, repeated provider timeouts, Redis failures and storage exhaustion.

Back up database and private storage consistently, encrypt backups and enforce a published retention policy. Test restoration with the exact encryption-key version before accepting real documents. Validate all ownership, refresh replay, duplicate-dose and booking conflict tests on PostgreSQL, including concurrent clients. The current local suite uses SQLite; PostgreSQL-specific behavior requires a separate host.

Run real Gemini evaluation and physical Android acceptance before release. Roll out first with synthetic documents. A successful container build, bundle export or test suite is not clinical validation.
