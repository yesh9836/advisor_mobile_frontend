# Android Emulator Requirement Setup

This guide explains the correct setup process for running this Flutter app on an Android emulator and connecting it to the local backend.

## Required Tools

Install these first:

```text
1. Flutter SDK
2. Android Studio
3. Android SDK Platform Tools
4. Android Emulator
5. AVD Android system image
6. Python backend requirements
```

## 1. Install Flutter

Download Flutter from:

```text
https://docs.flutter.dev/get-started/install
```

After installing Flutter, make sure `flutter` is available in PowerShell:

```powershell
flutter --version
```

Then check your setup:

```powershell
flutter doctor
```

Fix the important Android-related issues shown by `flutter doctor`.

## 2. Install Android Studio

Download Android Studio from:

```text
https://developer.android.com/studio
```

During installation, keep these selected:

```text
Android SDK
Android SDK Platform
Android Virtual Device
Android Emulator
```

After installation, open Android Studio once so it can finish downloading SDK components.

## 3. Install Android SDK Tools

In Android Studio:

```text
Android Studio > Settings > Languages & Frameworks > Android SDK
```

In the `SDK Platforms` tab, install a recent Android version, for example:

```text
Android 15 or Android 14
```

In the `SDK Tools` tab, install:

```text
Android SDK Build-Tools
Android SDK Command-line Tools
Android Emulator
Android SDK Platform-Tools
```

Click `Apply` and let Android Studio download everything.

## 4. Accept Android Licenses

Run:

```powershell
flutter doctor --android-licenses
```

Accept the licenses by typing `y` when asked.

Then run:

```powershell
flutter doctor
```

The Android toolchain should now be ready.

## 5. Create Android Emulator

Open Android Studio.

Go to:

```text
Tools > Device Manager
```

Click:

```text
Create Device
```

Recommended device:

```text
Pixel 7
```

Recommended system image:

```text
API 35 or API 34
x86_64 image
Google APIs image
```

Finish the wizard.

Then start the emulator from Device Manager by clicking the play button.

## 6. Confirm Flutter Sees the Emulator

With the emulator running, open PowerShell:

```powershell
flutter devices
```

You should see an Android emulator listed.

Example:

```text
emulator-5554    sdk gphone64 x86 64    android-x64
```

## 7. Install Backend Requirements

From the project root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.lock
```

If your project uses a `.env` file, make sure it is configured before starting the backend.

## 8. Start the Backend First

From the project root:

```powershell
cd backend
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Keep this terminal open.

The backend should be available on your computer at:

```text
http://localhost:8000
```

The Android emulator will reach it through:

```text
http://10.0.2.2:8000
```

## 9. Check Flutter API Base URL

Open:

```text
lib/services/api_service.dart
```

Make sure the Android emulator URL is:

```dart
ApiService({String? baseUrl})
  : _baseUrl = baseUrl ?? 'http://10.0.2.2:8000/api/v1';
```

This is required for Android emulator.

## 10. Run the Flutter App

Open a second terminal.

From the project root:

```powershell
cd flutter_frontend
flutter pub get
flutter run
```

Select the Android emulator if Flutter asks.

## Correct Running Order

Use this order every time:

```text
1. Start Android emulator
2. Start backend on port 8000
3. Confirm Flutter base URL uses 10.0.2.2
4. Run flutter pub get if dependencies changed
5. Run flutter run
6. Login in the app
7. Check dashboard/home APIs
```

## Common Problems and Fixes

### Emulator Does Not Show in Flutter

Run:

```powershell
flutter devices
```

If no emulator appears:

```text
1. Start emulator from Android Studio Device Manager.
2. Restart Android Studio.
3. Run flutter doctor.
4. Check Android SDK installation.
```

### App Cannot Connect to Backend

Check:

```text
1. Backend is running.
2. Backend is on port 8000.
3. API URL is http://10.0.2.2:8000/api/v1.
4. You are using Android emulator, not real phone.
5. Backend command uses --host 0.0.0.0.
```

### Login Fails

Check:

```text
1. Backend database has a user.
2. Email and password are correct.
3. Backend /api/v1/auth/login route is working.
4. App is pointed at the correct backend URL.
```

### Real Phone Does Not Connect

For a real Android phone, do not use `10.0.2.2`.

Use your computer Wi-Fi IP:

```text
http://YOUR_COMPUTER_WIFI_IP:8000/api/v1
```

Example:

```text
http://192.168.1.25:8000/api/v1
```

Your phone and computer must be on the same Wi-Fi network.

## Final Checklist

```text
[ ] Flutter installed
[ ] Android Studio installed
[ ] Android SDK installed
[ ] Android emulator created
[ ] Emulator visible in flutter devices
[ ] Backend requirements installed
[ ] Backend running on localhost:8000
[ ] Flutter API URL set to 10.0.2.2
[ ] flutter pub get completed
[ ] flutter run started successfully
```
