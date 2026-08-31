import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

void main() {
  const userJson =
      '{"id":1,"email":"advisor@example.com","name":"Advisor","role":"advisor"}';

  test('restores a session with a valid access cookie', () async {
    final api = _FakeApiService(getResponses: [http.Response(userJson, 200)]);

    final user = await AuthRepository(apiService: api).restoreSession();

    expect(user?.email, 'advisor@example.com');
    expect(api.postPaths, isEmpty);
    expect(api.restoredCookies, isTrue);
  });

  test('refreshes an expired access cookie and restores the session', () async {
    final api = _FakeApiService(
      getResponses: [http.Response('', 401), http.Response(userJson, 200)],
      postResponses: [http.Response('', 204)],
    );

    final user = await AuthRepository(apiService: api).restoreSession();

    expect(user?.name, 'Advisor');
    expect(api.postPaths, ['/auth/refresh']);
    expect(api.clearedCookies, isFalse);
  });

  test('clears an invalid refresh session and returns signed out', () async {
    final api = _FakeApiService(
      getResponses: [http.Response('', 401)],
      postResponses: [http.Response('', 401)],
    );

    final user = await AuthRepository(apiService: api).restoreSession();

    expect(user, isNull);
    expect(api.clearedCookies, isTrue);
  });
}

class _FakeApiService extends ApiService {
  _FakeApiService({
    List<http.Response>? getResponses,
    List<http.Response>? postResponses,
  }) : _getResponses = getResponses ?? [],
       _postResponses = postResponses ?? [];

  final List<http.Response> _getResponses;
  final List<http.Response> _postResponses;
  final List<String> postPaths = [];
  bool restoredCookies = false;
  bool clearedCookies = false;

  @override
  Future<void> restoreCookies() async => restoredCookies = true;

  @override
  Future<http.Response> get(
    String path, {
    bool retryUnauthorized = true,
  }) async => _getResponses.removeAt(0);

  @override
  Future<http.Response> post(
    String path, {
    Map<String, dynamic>? body,
    bool retryUnauthorized = true,
  }) async {
    postPaths.add(path);
    return _postResponses.removeAt(0);
  }

  @override
  Future<void> clearCookies() async => clearedCookies = true;
}
