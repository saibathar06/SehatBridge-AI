# Android development and APK builds

Use the installed lockfile with `npm ci` (Node 24 was used for verification). Dependencies target Expo SDK 58, with React/React Native and Expo modules selected using `npx expo install`, and the SDK-58 native speech-recognition release. Run `npx expo install --check` and `npx expo-doctor` when changing dependencies. Do not independently upgrade React Native or individual native Expo modules to a version outside the SDK compatibility table.

Expo Go is insufficient for native speech recognition and Android FCM. Build a development client:

```powershell
cd mobile
npx eas-cli@latest login
npx eas-cli@latest init
# Set the resulting project ID in EXPO_PUBLIC_EAS_PROJECT_ID
npx eas-cli@latest build --platform android --profile development
npx expo start --dev-client
```

For an installable standalone APK:

```powershell
# Set EXPO_PUBLIC_API_URL to the hosted HTTPS API before building.
npx eas-cli@latest build --platform android --profile preview
```

The preview profile uses `android.buildType=apk`. Production uses an AAB. EAS authentication/project ownership and Android signing credentials are required. No signing credential is committed. An APK is not claimed until EAS returns a successful build and the artifact is installed/tested.

Alternatively, install the matching Android SDK, JDK supported by React Native/Gradle, and device drivers, then `npx expo run:android`. A local Java installation alone does not verify the full native toolchain. An Android build needs network downloads for Gradle and Maven artifacts.

On a physical phone, enable USB debugging or install the EAS APK. Use a reachable LAN backend for development, not `localhost`. The generated debug Android manifest permits cleartext development traffic; release builds require the configured HTTPS API. Prefer an HTTPS development tunnel when using authorized medical data. Never loosen release network security.

Physical-device acceptance must check Hindi/English speech-service availability, microphone denial, silence, airplane mode, transcript correction, TTS voice installation, play/stop/replay, local alerts after background/reboot, quiet hours, treatment edits, timezone changes, denied notifications, battery optimization and the 48-alert bound. Check `docs/verification.md` before claiming success.
