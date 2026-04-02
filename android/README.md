# ResonantOS Android App

A WebView-based Android app that provides mobile access to the ResonantOS Dashboard.

## APK Location
`app-debug.apk` (5.5 MB)

## Installation on Android Phone

1. **Transfer the APK to your phone:**
   - Connect phone via USB, copy `app-debug.apk` to Downloads
   - Or send via Telegram/WhatsApp/email to yourself
   - Or use ADB: `adb install app-debug.apk`

2. **Allow installation from unknown sources:**
   - Go to Settings → Security
   - Enable "Install unknown apps" for your file manager

3. **Install the APK:**
   - Open the file manager
   - Navigate to where you saved the APK
   - Tap to install

## Usage

### Default URL
The app should load `http://YOUR_HOST_IP:19100`

To use the app:

1. **Make sure the dashboard is running** on your computer
2. **Both devices on same WiFi network**
3. **Find your computer's local IP:**
   - Mac: System Preferences → Network → WiFi → IP Address
   - Or run: `ifconfig | grep 'inet ' | grep -v 127.0.0.1`

### Changing the Dashboard URL

The app defaults to `http://YOUR_HOST_IP:19100`. To change it:

1. Edit `android-app/app/src/main/java/com/resonantos/dashboard/MainActivity.java`
2. Change `DEFAULT_URL` to your IP address
3. Rebuild the APK

Or, access the dashboard URL remotely using:
- ngrok tunnel
- Tailscale/ZeroTier VPN
- Port forwarding on router

## Features

- ✅ WebView wrapper for ResonantOS Dashboard
- ✅ Pull-to-refresh
- ✅ Back button navigation within the app
- ✅ Session persistence (cookies saved)
- ✅ Full-screen experience (no browser chrome)
- ✅ ResonantOS robot icon

## Building from Source

Requirements:
- Java 17+ (`brew install openjdk@17`)
- Android SDK (`brew install --cask android-commandlinetools`)

```bash
cd android-app
export JAVA_HOME=/opt/homebrew/opt/openjdk@17
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
gradle assembleDebug
```

APK will be at: `app/build/outputs/apk/debug/app-debug.apk`

## Troubleshooting

**App can't connect to dashboard:**
- Check both devices are on the same WiFi
- Verify the dashboard is running: `curl http://YOUR_IP:19100`
- Make sure firewall allows port 19100

**White screen / loading forever:**
- Pull down to refresh
- Check network connection
- Verify the URL is correct

**App crashes:**
- Clear app data in Android Settings → Apps → ResonantOS
- Reinstall the APK
