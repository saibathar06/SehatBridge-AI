# Run locally on Windows

Open PowerShell in `C:\Users\saiba\Documents\ChatGPT\SehatBridge AI`. The Python environment, npm packages, local development secrets and mobile emulator URL have already been created in this workspace.

## Terminal 1: API

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-backend.ps1
```

Open `http://127.0.0.1:8000/docs`. `/health` and `/ready` should return successful responses. The script migrates the development database before starting. It binds port 8000 to the local network so a phone can reach it. Use synthetic documents over development HTTP.

If port 8000 is already occupied by a previous backend, keep that process or stop it with Ctrl+C in its terminal before restarting.

## Terminal 2: processing/reminder worker

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-worker.ps1
```

Keep both backend terminals open. Console OTP codes are printed only in the API terminal in development. Registration and login work without a Gemini key. Actual extraction and AI explanations require `GEMINI_API_KEY` and `GEMINI_MODEL` in `backend/.env`, followed by restarting API and worker. There is no fake extraction fallback.

When you enable `RECAPTCHA_ENABLED`, configure your Google v2 key pair and checkbox-page origin first. See [reCAPTCHA setup](recaptcha.md). The Android launch script forwards port 8000 so a localhost-registered checkbox page can reach the backend through ADB.

## Terminal 3: Android app

First start an emulator using Android Studio → Device Manager. This PC has an AVD named `Resizable_Experimental`. Alternatively, connect an Android phone with USB debugging enabled and accept its authorization prompt.

For the emulator, `mobile/.env` uses:

```dotenv
EXPO_PUBLIC_API_URL=http://10.0.2.2:8000/api/v1
```

For a physical USB-connected phone, run `adb reverse tcp:8000 tcp:8000` and use `http://127.0.0.1:8000/api/v1`, or configure the computer's reachable LAN IPv4 address. Restart Metro after changing the public environment.

Then run from the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-android.ps1
```

This builds and installs the native debug app, forwards Metro's port, and starts the development server. It reuses the checksum-verified Gradle 9.4.1 copy under `.local-build` when compatible with the native project. First build still needs Android/Maven/SDK downloads. Keep the terminal open after Metro starts. Subsequent JavaScript-only edits can use `cd mobile; npx expo start --dev-client --localhost --android` without rebuilding native code.

Expo Go cannot run the native speech-recognition module. A successful Metro server alone does not mean the Android app has been built or installed.

## Current build/network evidence

On 19 October 2026, a normal Windows Schannel download reproduced `SEC_E_DECRYPT_FAILURE`, independently of Java. Short HTTPS requests and the server certificate validation succeeded; Windows reported no explicit WinHTTP proxy. The Gradle archive was recovered using small HTTPS ranges and matched the official SHA-256:

`2ab2958f2a1e51120c326cad6f385153bb11ee93b3c216c5fccebfdfbb7ec6cb`

The next native build reached dependency resolution but failed to resolve `repo.maven.apache.org` for Kotlin build dependencies. This is a separate observed DNS failure. These observations do not establish which router, adapter, driver, security layer or local component caused the earlier TLS failures. A comparison network was declined; no network adapter or security settings have been changed.

To check the current DNS blocker in your terminal:

```powershell
Resolve-DnsName repo.maven.apache.org
Test-NetConnection repo.maven.apache.org -Port 443
```

Do not disable certificate checks. Gradle supports checksum verification through `distributionSha256Sum`; see the [official Gradle Wrapper documentation](https://docs.gradle.org/current/userguide/gradle_wrapper.html).

On 20 October, the reported Maven download failed with Java TLS `bad_record_mac / Tag mismatch` for `kotlin-gradle-plugin-2.2.21-gradle813.jar`. The artifact was recovered over verified HTTPS ranges, matched Maven Central's published SHA-1 `c4379902f2048e2421f9df070f2f93e154233576`, and was placed in the local Gradle cache. The retry passed that failure, then stopped because React Native's build plugins require a JDK 17 compile toolchain; installed JDKs 25 and 26 did not satisfy that requirement, and automatic toolchain download failed. `run-android.ps1` now detects an extracted `.local-build/jdk-17*` directory and passes it as an explicit Gradle toolchain path while retaining the current Java used to launch Gradle.

The active USB Wi-Fi receiver reports `802.11n USB Wireless LAN Card`, Ralink, Microsoft driver `5.1.22.0` dated 14 August 2007. The timing of the user's failures makes the receiver/driver worth investigating, but neither that date nor the TLS error establishes the root cause. Check Windows Update's optional driver updates or the receiver manufacturer's exact-model driver. No adapter, driver, routing, or security settings were changed during diagnosis.

The local Temurin JDK 17.0.20.1 archive was subsequently recovered with verified HTTPS ranges and matched Adoptium's published SHA-256 `e53a79c3c3d86865bd7e787903884331068e71321714ffd44f145785affc7cb0`. It is extracted under `.local-build/jdk-17.0.20.1+1`; `javac -version` succeeds. The subsequent Gradle retry reached plugin compilation using the explicitly configured toolchain. This does not by itself establish a successful APK build.

The next retry exposed the same TLS integrity failure downloading Google's `builder-9.2.1.jar` and Maven Central's `kotlin-compiler-embeddable-2.2.0.jar`. Both were subsequently recovered over verified HTTPS and checked against their respective repository SHA-1 sidecars before caching. The range downloader now requests `Accept-Encoding: identity` because Google's compressed representation changes the byte ranges; it also validates the exact returned `Content-Range`. These are download workarounds, not a confirmed repair of the network receiver or TLS root cause.

The latest retry compiled the settings plugins and advanced to the React Native Gradle plugin, then failed with the same TLS `Tag mismatch` downloading `kotlin-gradle-plugin-2.2.10-gradle813.jar` from Maven Central. An APK was not produced by these attempts. The user reports that Ethernet worked before the switch to this USB Wi-Fi receiver; that comparison strengthens the receiver/driver/Wi-Fi-path hypothesis without isolating one cause.

## First local checks

1. Register and verify using the development code printed in Terminal 1.
2. Save a clearly synthetic profile; confirm Home loads authenticated data.
3. Open appointment/lab/pharmacy demonstrations and save/cancel simulated transactions.
4. Enable notification permission and send the 10-second test reminder.
5. Configure Gemini before attempting real extraction. Without it, confirm that the saved upload shows an explicit configuration error.
6. Test Hindi recognition and TTS on a physical Android phone; emulator results do not replace physical-device acceptance.

Close servers with Ctrl+C in their terminals. Never commit `.env`, provider credentials or private test documents.
