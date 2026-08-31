import 'package:flutter_frontend/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

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

  test(
    'refreshes one expired session and retries concurrent requests',
    () async {
      final cookieStore = CookieStore()
        ..cookies.addAll({
          'access_token': 'expired',
          'refresh_token': 'refresh123',
          'csrf_token': 'csrf123',
        });
      var refreshCalls = 0;
      var protectedCalls = 0;
      final client = MockClient((request) async {
        if (request.url.path.endsWith('/auth/refresh')) {
          refreshCalls++;
          await Future<void>.delayed(const Duration(milliseconds: 10));
          return http.Response(
            '',
            204,
            headers: {
              'set-cookie':
                  'access_token=fresh; Path=/,csrf_token=fresh-csrf; Path=/',
            },
          );
        }

        protectedCalls++;
        final cookieHeader =
            request.headers['Cookie'] ?? request.headers['cookie'] ?? '';
        return cookieHeader.contains('access_token=fresh')
            ? http.Response('{"ok":true}', 200)
            : http.Response('Could not validate credentials', 401);
      });
      final api = ApiService(
        baseUrl: 'https://api.example.test/api/v1',
        client: client,
        cookieStore: cookieStore,
      );

      final responses = await Future.wait([
        api.get('/protected/one'),
        api.get('/protected/two'),
      ]);

      expect(
        responses.map((response) => response.statusCode),
        everyElement(200),
      );
      expect(refreshCalls, 1);
      expect(protectedCalls, 4);
      expect(cookieStore.cookies['access_token'], 'fresh');
    },
  );

  test('normalizes transport failures into a user-facing error', () async {
    final api = ApiService(
      baseUrl: 'https://api.example.test/api/v1',
      client: MockClient((_) async => throw http.ClientException('offline')),
      cookieStore: CookieStore(),
    );

    await expectLater(
      api.get('/licenses/'),
      throwsA(
        isA<ApiException>().having(
          (error) => error.message,
          'message',
          contains('Unable to reach the server'),
        ),
      ),
    );
  });

  test('times out stalled endpoint requests', () async {
    final api = ApiService(
      baseUrl: 'https://api.example.test/api/v1',
      client: MockClient((_) async {
        await Future<void>.delayed(const Duration(milliseconds: 100));
        return http.Response('{}', 200);
      }),
      cookieStore: CookieStore(),
      requestTimeout: const Duration(milliseconds: 5),
    );

    await expectLater(
      api.get('/leads/'),
      throwsA(
        isA<ApiException>().having(
          (error) => error.message,
          'message',
          contains('timed out'),
        ),
      ),
    );
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
