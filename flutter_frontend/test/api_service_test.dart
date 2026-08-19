import 'package:flutter_frontend/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

void main() {
  test('cookie store captures csrf token from set-cookie headers', () async {
    final cookieStore = CookieStore();
    final response = http.Response(
      '',
      200,
      headers: {'set-cookie': 'csrf_token=abc123; Path=/; HttpOnly'},
    );

    await cookieStore.updateFromResponse(response);

    expect(cookieStore.cookies['csrf_token'], 'abc123');
    expect(cookieStore.getHeaderValue(), 'csrf_token=abc123');
  });

  test(
    'cookie store parses combined auth cookies without comma whitespace',
    () async {
      final cookieStore = CookieStore();
      final response = http.Response(
        '',
        204,
        headers: {
          'set-cookie':
              'access_token=access123; Path=/; HttpOnly; '
              'Expires=Sun, 09 Aug 2026 12:00:00 GMT,'
              'refresh_token=refresh123; Path=/api/v1/auth/refresh; HttpOnly,'
              'csrf_token=csrf123; Path=/',
        },
      );

      await cookieStore.updateFromResponse(response);

      expect(cookieStore.cookies, {
        'access_token': 'access123',
        'refresh_token': 'refresh123',
        'csrf_token': 'csrf123',
      });
      expect(cookieStore.csrfToken, 'csrf123');
      expect(
        cookieStore.getHeaderValue(),
        'access_token=access123; refresh_token=refresh123; csrf_token=csrf123',
      );
    },
  );

  test('cookie store restores persisted cookies after app restart', () async {
    final persistence = _MemoryCookiePersistence();
    final firstStore = CookieStore(persistence: persistence);
    await firstStore.updateFromResponse(
      http.Response(
        '',
        204,
        headers: {
          'set-cookie':
              'access_token=access123; Path=/,csrf_token=csrf123; Path=/',
        },
      ),
    );

    final restartedStore = CookieStore(persistence: persistence);
    await restartedStore.restore();

    expect(restartedStore.cookies['access_token'], 'access123');
    expect(restartedStore.csrfToken, 'csrf123');
  });
}

class _MemoryCookiePersistence implements CookiePersistence {
  Map<String, String> values = {};

  @override
  Future<void> clear() async => values.clear();

  @override
  Future<Map<String, String>> read() async => Map.of(values);

  @override
  Future<void> write(Map<String, String> cookies) async {
    values = Map.of(cookies);
  }
}
