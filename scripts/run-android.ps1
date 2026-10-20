$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskMobile = Join-Path $taskRoot 'mobile'
$taskSdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
$taskAdb = Join-Path $taskSdk 'platform-tools\adb.exe'
if (-not (Test-Path -LiteralPath $taskAdb)) { throw 'Install Android SDK platform-tools, then set ANDROID_HOME.' }
if (-not (Test-Path -LiteralPath (Join-Path $taskMobile 'node_modules\expo\package.json'))) {
    throw 'Mobile dependencies missing. Run npm ci in mobile first.'
}
$env:ANDROID_HOME = $taskSdk
$env:GRADLE_USER_HOME = Join-Path $taskRoot '.local-build\gradle-home'
& $taskAdb start-server
$taskDevices = & $taskAdb devices
if (-not ($taskDevices | Where-Object { $_ -match '\sdevice$' })) {
    throw 'No Android device connected. Start an emulator in Android Studio Device Manager, or connect a USB-debugging-enabled Android phone, then retry.'
}
Push-Location $taskMobile
try {
    if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
    if (-not (Test-Path -LiteralPath 'android\gradlew.bat')) {
        & npx.cmd expo prebuild --platform android --no-install
        if ($LASTEXITCODE -ne 0) { throw 'Android native generation failed.' }
    }
    $taskRecoveredGradle = Join-Path $taskRoot '.local-build\gradle-9.4.1\bin\gradle.bat'
    # Use the recovered copy only if it matches this native project's declared version.
    $taskProperties = Get-Content -LiteralPath 'android\gradle\wrapper\gradle-wrapper.properties' -Raw
    $taskGradle = if ((Test-Path -LiteralPath $taskRecoveredGradle) -and $taskProperties.Contains('gradle-9.4.1-bin.zip')) {
        $taskRecoveredGradle
    } else { Join-Path $taskMobile 'android\gradlew.bat' }
    # React Native's Gradle plugin compiles with JDK 17, even when Gradle itself
    # runs on a newer Java. Reuse a verified local toolchain when available.
    $taskJdk17 = Get-ChildItem -LiteralPath (Join-Path $taskRoot '.local-build') -Directory -Filter 'jdk-17*' |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'bin\javac.exe') } |
        Sort-Object Name -Descending | Select-Object -First 1
    $taskToolchainArgs = @()
    if ($taskJdk17) {
        $taskJdkPath = $taskJdk17.FullName.Replace('\', '/')
        $taskToolchainArgs = @("-Porg.gradle.java.installations.paths=$taskJdkPath")
    }
    Push-Location 'android'
    try {
        & $taskGradle ':app:installDebug' '--no-daemon' '--max-workers=2' '--console=plain' @taskToolchainArgs
        if ($LASTEXITCODE -ne 0) { throw 'Android build failed. Read the first download/compile error above. The native app cannot launch until this succeeds.' }
    } finally { Pop-Location }
    & $taskAdb reverse tcp:8081 tcp:8081
    # Allows a localhost-registered reCAPTCHA checkbox page to reach the local API.
    & $taskAdb reverse tcp:8000 tcp:8000
    Write-Host 'Starting Metro. Keep this terminal open; Ctrl+C stops it.'
    & npx.cmd expo start --dev-client --localhost --android --port 8081
} finally { Pop-Location }
