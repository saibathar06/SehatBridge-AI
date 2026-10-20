# Firebase Android setup

1. Create a Firebase project and register Android application `com.sehatbridge.patient`.
2. Download its public client `google-services.json`. Supply its absolute path through build-time `GOOGLE_SERVICES_JSON`. This file is ignored by Git. It is not a server service-account credential.
3. Enable Firebase Cloud Messaging. Create a narrowly scoped server identity with permission to send messages. Prefer managed workload identity for hosting; the included adapter accepts a mounted service-account JSON path through backend `FIREBASE_CREDENTIALS`.
4. Keep the service account outside the repository, Expo environment and APK. Mount it read-only into API/worker containers or adapt `send_fcm` to workload identity.
5. Rebuild the Android development client after setting Firebase client configuration. Open Settings, grant notification permission and select remote FCM. The app retrieves the native device token through Expo Notifications and registers it to the authenticated patient.
6. The app handles token refresh, deregisters its stored registration when switching to local delivery or signing out, and uses SecureStore for the registration ID. Backend delivery attempts contain sanitized status without medical content or tokens.
7. Keep the worker running. FCM sends generic lock-screen text for due doses in a two-minute freshness window. Sends are recorded once per dose/device. Failed attempts remain visible in encrypted delivery records; delivery is not claimed merely because an API request was accepted.

Remote selection cancels local scheduled alerts at reconciliation to avoid duplicate reminder channels. Local delivery is the default demonstration path. FCM requires real project credentials and a physical Android build; provider acceptance does not guarantee OS presentation. Test a real due dose, token refresh, permission denial, revoked token and offline behavior before signing off.

Reference: [Expo notification requirements](https://docs.expo.dev/versions/latest/sdk/notifications/) and [Firebase Admin SDK](https://firebase.google.com/docs/cloud-messaging/send/admin-sdk).
