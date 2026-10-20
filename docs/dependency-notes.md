# Dependency decisions and audit

Verified on 18 October 2026 using the npm registry, Expo's SDK compatibility table and a clean Expo Doctor run. Use the lockfiles, not an unbounded upgrade of native packages.

- Expo **58.0.16**, React **19.3.0**, React Native **0.88.0**. Expo and four SDK modules received compatible patch updates on 19 October while adding WebView.
- `react-native-webview` **14.0.1** follows the Expo SDK compatibility resolver and hosts the reCAPTCHA v2 checkbox window.
- Expo packages use the versions selected by `expo install`; speech recognition uses the SDK-58 release **58.0.0**.
- TypeScript **6.0.3** follows Expo's compatibility table; the registry's TypeScript 7 release was deliberately replaced after the compatibility check rejected it.
- React DOM **19.3.0** is a development/toolchain peer pinned to match React. It does not create a website target. Only Android/iOS are configured.
- Native optional peers (Reanimated/Worklets/Linking/Font) are pinned to Expo's table instead of accepting npm's unconstrained newest peer selection.
- Xcode tooling's UUID dependency is overridden within the CommonJS-compatible 11.x line to address its published buffer-bounds advisory. Android native generation and bundle export were verified after this change.
- Python dependencies are installed at current available versions and recorded exactly in `backend/requirements.lock.txt`. `pip check` passed.

The final raw npm audit is saved in [mobile-dependency-audit.json](mobile-dependency-audit.json). It still reports high-severity advisories propagated through the current Expo toolchain from:

1. `braces <=3.0.3`: deeply nested pattern denial of service. The registry's latest stable release is 3.0.3; no patched stable release was available at verification time.
2. `node-forge <=1.4.0`: RSA signature verification issue. Latest stable is 1.4.0; no patched stable release was available at verification time.

The audit counts dependent packages as affected as well. Its proposed `--force` “fix” is a downgrade to Expo 44 / React Native 0.72 and is incompatible with this project's stack. That downgrade was not applied. Track upstream patched releases and rerun the native compatibility/build checks before release. Build tooling should handle trusted inputs and run in an isolated CI environment. The current audit is a known release limitation, not a clean security bill.

Some large dependency downloads repeatedly failed with TLS record corruption in this environment. `scripts/download_verified.py` provides small HTTPS range requests with certificate verification and registry checksum validation to recover packages; it does not disable transport security or alter dependency source code.
