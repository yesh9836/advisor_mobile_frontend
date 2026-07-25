# Connecting Flutter Android Emulator to the Backend

This Flutter app connects to the local backend through:

```text
http://10.0.2.2:8000/api/v1
```

The value is defined in:

```text
lib/services/api_service.dart
```

```dart
ApiService({String? baseUrl})
  : _baseUrl = baseUrl ?? 'http://10.0.2.2:8000/api/v1';
```

## Why `10.0.2.2` Is Used

Inside an Android emulator, `localhost` means the emulator itself, not your computer.

Android provides `10.0.2.2` as a special address that points back to your computer.

So this emulator URL:

```text
http://10.0.2.2:8000/api/v1
```

connects to this backend URL on your computer:

```text
http://localhost:8000/api/v1
```

## Start the Backend

From the project root:

```powershell
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend should now be available at:

```text
http://localhost:8000
```

API routes are under:

```text
http://localhost:8000/api/v1
```

## Run the Flutter App

Open another terminal:

```powershell
cd flutter_frontend
flutter run
```

Choose your Android emulator when Flutter asks for a device.

## APIs Used by the App

After login, the app calls backend routes such as:

```text
POST /api/v1/auth/login
GET  /api/v1/auth/me
GET  /api/v1/leads/dashboard/summary
GET  /api/v1/leads/
GET  /api/v1/purchases/packages
GET  /api/v1/goals/me
```

The Flutter app stores backend cookies in `CookieStore`, so after login the next API requests automatically include the session cookie and CSRF token.

## For Different Devices

Use this backend URL depending on where the app is running:

```text
Android emulator: http://10.0.2.2:8000/api/v1
iOS simulator:    http://localhost:8000/api/v1
Real phone:       http://YOUR_COMPUTER_WIFI_IP:8000/api/v1
```

Example for a real phone:

```text
http://192.168.1.25:8000/api/v1
```

For a real phone, your phone and computer must be on the same Wi-Fi network.

## Common Problems

If the emulator cannot connect:

1. Make sure the backend is running on port `8000`.
2. Make sure Flutter is using `http://10.0.2.2:8000/api/v1`.
3. Make sure the backend command uses `--host 0.0.0.0`.
4. Restart the Flutter app after changing the API base URL.
5. Check that the Android emulator has internet/network access.

## Quick Checklist

```text
[ ] Backend running on localhost:8000
[ ] Flutter base URL is http://10.0.2.2:8000/api/v1
[ ] Android emulator is selected
[ ] Login works
[ ] Dashboard APIs load after login
```
