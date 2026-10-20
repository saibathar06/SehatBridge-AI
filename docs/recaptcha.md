# Google reCAPTCHA v2 checkbox

SehatBridge adapts the user's AntarTalk modal/WebView pattern. It uses the **web v2 “I'm not a robot” checkbox**, not v3, Invisible reCAPTCHA, or the deprecated native SafetyNet Android key. No AntarTalk credentials or source files were changed.

The mobile app reads `GET /api/v1/auth/recaptcha-config`. When enabled, it opens the backend's public `/api/v1/auth/mobile-recaptcha` page in an isolated native WebView modal. Google displays its actual checkbox and any image/audio challenge. Only a token returns to the native form; no account credentials or medical records enter the page. After submission, the backend verifies the token with Google's `siteverify` service and checks the exact issued hostname before registration, login or OTP email sending proceeds.

The secret key stays on the backend. The site key is public and appears only in the checkbox HTML. There are no reCAPTCHA secrets or duplicated key settings in `mobile/.env`.

## Configure your keys

1. Open the [Google reCAPTCHA admin console](https://www.google.com/recaptcha/admin/create). Register a separate SehatBridge key using **reCAPTCHA v2 → “I'm not a robot” Checkbox**.
2. For local development, allow `localhost` in Google's domain configuration. For deployment, add the actual hostname serving your backend's checkbox page. Domains contain neither protocol nor port nor URL path. Keep Google's domain validation enabled.
3. Add the following to `backend/.env` without changing existing authentication, encryption, Gemini or SMTP settings:

```dotenv
RECAPTCHA_ENABLED=true
RECAPTCHA_SITE_KEY=YOUR_GOOGLE_V2_SITE_KEY
RECAPTCHA_SECRET_KEY=YOUR_GOOGLE_V2_SECRET_KEY
RECAPTCHA_PUBLIC_ORIGIN=http://localhost:8000
RECAPTCHA_ALLOWED_HOSTNAMES=["localhost"]
```

For production, use a public HTTPS origin and its exact hostname:

```dotenv
RECAPTCHA_PUBLIC_ORIGIN=https://api.your-domain.example
RECAPTCHA_ALLOWED_HOSTNAMES=["api.your-domain.example"]
```

Production startup refuses disabled protection, incomplete keys, localhost/HTTP origins, and Google's public always-pass site key. Disabling protection is permitted only in development and is explicit in `/auth/recaptcha-config`; it is not an automatic fallback when Google is unavailable.

## Local Android setup

Rebuild the Android development app because `react-native-webview` is a newly added native dependency. `scripts/run-android.ps1` installs the debug build and forwards both Metro port 8081 and backend port 8000 through ADB. To forward manually:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" reverse tcp:8000 tcp:8000
```

This lets the device WebView reach `http://localhost:8000` while your ordinary emulator API URL can remain `http://10.0.2.2:8000/api/v1`. A physical phone without ADB forwarding needs the configured public HTTPS checkbox origin; the phone's localhost otherwise refers to the phone itself. Registering a random LAN IP instead of a hostname is not the documented local path.

Restart the backend after editing its environment and restart Metro after installing the dependency. No actual `.env` was overwritten by this feature change.

## Behavior and verification

- Registration, login, first OTP send, resend and password-reset email requests require a fresh check when enabled. Existing OTP entry and refresh-token/session flows remain independently protected by their existing expiry/attempt/rate rules.
- The native token is memory-only, cleared after every protected request attempt, on form-mode changes, and after 110 seconds. Google checks the token's two-minute single-use lifetime. `challenge_ts` describes when the challenge loaded, so a slow human image challenge is not incorrectly rejected solely because that timestamp is old.
- Missing/failed/reused tokens and wrong hostnames return 403. Google timeouts or invalid server credentials return 503. No OTP is sent and no registration is persisted if verification fails.
- Public configuration load failures block protected form submission and offer retry. The WebView has a 30-second initial-load timeout, bounded token messages, exact-page bridge checks, top-level navigation restrictions, Google challenge frame allowlisting, and no local-file access. Closing/reopening invalidates old window callbacks.
- The CAPTCHA page has a nonce-based script policy, no-store headers and Google's privacy/terms links. Those links are also available through native controls.
- Backend tests use explicit provider mocks for accepted/rejected/reused/expired/wrong-host responses and failure modes; mobile tests cover URL/message/navigation gates. These are not claims of a live Google challenge passing on a physical Android device.

To verify live: configure your key pair, rebuild/install, open login or registration, solve the checkbox, submit once, inspect success, then test expiration, wrong hostname, offline Google access and email resend with a fresh check. Brevo configuration remains separate. Existing Android dependency-download/DNS problems may still need resolution before native installation.

References: [Google verification contract](https://developers.google.com/recaptcha/docs/verify), [domain validation](https://developers.google.com/recaptcha/docs/domain_validation), [v2 checkbox type](https://developers.google.com/recaptcha/docs/versions), and [CSP/testing FAQ](https://developers.google.com/recaptcha/docs/faq).
