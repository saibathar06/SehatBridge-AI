# Verification and remaining acceptance

This document distinguishes implemented paths from externally verified integrations. It must be updated with actual command results before delivery.

## Implemented

- Independent FastAPI REST API and durable document worker, strict schemas, initial Alembic migration, PostgreSQL deployment configuration.
- Argon2id passwords; email OTP; rotating/revocable refresh tokens; encrypted medical fields/files; patient-scoped APIs; rate and payload limits.
- Ordered multi-image upload with pre-upload reordering/rotation/removal/addition; ordered PDF splitting; encrypted source access and rendered PDF previews.
- Official Gemini multimodal structured extraction, bounded batches, source/uncertainty validation, recoverable failure/retry; no fake provider fallback.
- Editable review sections, explicit revision-checked confirmation, normalized treatment/medicine/schedule/dose/event tables and auditable schedule replacement.
- Simple daily schedules with confirmed dates/times/timezones; local notification intent and bounded reconciliation; quiet hours; generic lock-screen text; FCM adapter/device lifecycle/failure records.
- Native Hindi/English speech recognition, transcript correction, record-grounded text chat, native TTS voice checks and play/stop/replay. History is opt-in and clearable.
- Synthetic doctor/lab directory, availability, database-constrained booking/cancellation and pharmacy inventory/cart/orders.

## Locally verified

The backend suite passed **60 tests** with synthetic users, documents and explicit test doubles. It covers authentication/OTP/refresh replay/logout/reset, ownership, private files, image order, all PDF pages and previews, malformed upload rejection, strict output validation, ambiguity, confirmation, schedule replacement, dose idempotency/corrections, timezone/DST/quiet hours, booking conflicts, AES-GCM tampering/owner binding, rate limits, patient-grounded Hindi responses, missing Gemini configuration, timeout/quota recovery, sanitized notification failures, unsupported-frequency blocking, chat privacy, account deletion and reminder preference intent.

Both Alembic migrations, metadata drift checking and synthetic catalogue seeding were executed on SQLite. Python dependency checks passed. Mobile TypeScript checking and **9 mobile tests** passed. Expo's dependency compatibility check passed and **Expo Doctor passed 20/20 checks**. Native Android project generation succeeded. The Android Hermes production bundle exported successfully (2.8 MB at the recorded verification point). Full API schemas and the route reference were generated from the running application schema.

The local debug APK build was attempted using the installed Android SDK and JDK 25. It stopped while downloading Gradle 9.4.1 with `javax.net.ssl.SSLException: bad_record_mac / Tag mismatch`. This is a download/transport failure, not a completed native compile. **No APK has been produced.** ADB reported no connected Android devices; one emulator configuration is installed but has not been used for acceptance testing. Re-run the native build on a stable network or use the documented EAS path with your account/project credentials.

The npm audit still reports **19 high-severity affected dependency entries**, propagated from two unpatched upstream toolchain packages. See [dependency decisions and audit](dependency-notes.md). Compatible UUID remediation was applied; an incompatible SDK downgrade was not.

## Credentials or external environment required

reCAPTCHA update on 19 October 2026: native checkbox-modal integration, backend Google verification, hostname/configuration checks and new authentication guards are implemented. The backend regression suite includes 24 reCAPTCHA cases, and mobile tests include five CAPTCHA configuration/message/navigation cases. Live verification requires a separately configured Google v2 checkbox key pair and a rebuilt Android app; no live Google/physical-device challenge result is claimed. See [reCAPTCHA setup](recaptcha.md).

Update on 19 October 2026: the Gradle 9.4.1 archive was recovered through verified HTTPS ranges and extracted locally. API `/health` and `/ready` were checked successfully, and the emulator booted. The next Android build reached Kotlin dependency resolution but failed DNS lookup for `repo.maven.apache.org`. No APK has been produced. The earlier interactive server/emulator sessions have stopped; use [the local launch scripts](local-running.md) from your own terminals.

- **Gemini live extraction/explanation and field-level accuracy:** no API key has been provided. The eight-case synthetic set and real-provider evaluation runner are included. No numerical AI accuracy is claimed. Real difficult handwriting needs properly authorized, de-identified, independently annotated fixtures and held-out regression tests; synthetic strokes are not a handwriting benchmark.
- **SMTP:** console OTP works only in development. Real mail delivery, spam handling and provider quotas need configured credentials.
- **PostgreSQL/Redis/Docker:** no Docker installation is available in this environment. Validate migration, row-lock concurrency, distributed rate limiting, restoration and container deployment on a suitable host.
- **FCM:** server/client Firebase credentials have not been supplied. Sending and real Android presentation are unverified.
- **Android APK/EAS:** local build currently blocked by the Gradle TLS download failure. Alternatively, EAS requires account/project/signing configuration. An exported JavaScript bundle is not an APK.
- **Physical Hindi voice/reminder flow:** must be run on a physical Android phone with the selected speech service and TTS packs. No physical-device result is claimed.

## Deliberate MVP limits

Only recognized simple daily medicine frequencies activate automatic schedules. Weekly, alternating-day, interval, tapering and as-needed regimens remain unscheduled. Dates are explicit and limited to a year per schedule. A schedule creates future doses from its activation time; it does not invent historical dose instances. Quiet hours suppress delivery instead of changing treatment times.

The application shell and most forms are currently English; the assistant supports Hindi/English recognition, text answers and speech, and Profile stores the preferred assistant language. A fully translated Hindi application shell is additional localization work.

Local reminders cover up to seven days and 48 alerts. App foreground refresh is required. Device-specific battery restrictions, exact-alarm policy, reboot and OS delivery must be verified; this app does not claim unlimited/offline multi-month alarms. Local and remote are alternative channels. Multi-device preference/deletion changes propagate when each device next reconciles. The current remote worker records one send attempt per dose/device and does not blindly retry failed FCM sends.

No verified drug-information provider is connected, so side-effect questions explicitly direct verification instead of giving unsupported drug facts. Doctor/lab/pharmacy data and all transactions are synthetic. There is no live clinician, laboratory, pharmacy, payment or delivery integration.

Onboarding illustrations have been represented by accessible native icon compositions while preserving the reference structure and palette. The supplied PNGs remain available for future licensed illustration extraction/refinement. Full screenshot comparison and device layout QA remain to be performed on the actual native build.


