import 'dart:convert';
import 'dart:async';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

abstract class CookiePersistence {
  Future<Map<String, String>> read();

  Future<void> write(Map<String, String> cookies);

  Future<void> clear();
}

class SecureCookiePersistence implements CookiePersistence {
  SecureCookiePersistence({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  static const _storageKey = 'spectaculeads_auth_cookies_v1';
  final FlutterSecureStorage _storage;

  @override
  Future<Map<String, String>> read() async {
    final encoded = await _storage.read(key: _storageKey);
    if (encoded == null || encoded.isEmpty) return {};
    try {
      final decoded = jsonDecode(encoded) as Map<String, dynamic>;
      return decoded.map((key, value) => MapEntry(key, value.toString()));
    } catch (_) {
      await clear();
      return {};
    }
  }

  @override
  Future<void> write(Map<String, String> cookies) {
    return _storage.write(key: _storageKey, value: jsonEncode(cookies));
  }

  @override
  Future<void> clear() => _storage.delete(key: _storageKey);
}

class CookieStore {
  CookieStore({this.persistence});

  final Map<String, String> cookies = {};
  final CookiePersistence? persistence;

  Future<void> restore() async {
    final restored = await persistence?.read();
    if (restored == null) return;
    cookies
      ..clear()
      ..addAll(restored);
  }

  Future<void> updateFromResponse(http.Response response) async {
    final rawSetCookie = response.headers['set-cookie'];
    if (rawSetCookie == null || rawSetCookie.isEmpty) return;

    // package:http combines repeated Set-Cookie headers with a comma and does
    // not guarantee whitespace after it. Only split commas that are followed
    // by another cookie name so commas inside Expires dates remain intact.
    final cookieDefinitions = rawSetCookie.split(RegExp(r',\s*(?=[^;,=\s]+=)'));
    for (final definition in cookieDefinitions) {
      final cookiePart = definition.split(';').first.trim();
      final separatorIndex = cookiePart.indexOf('=');
      if (separatorIndex < 0) continue;
      cookies[cookiePart.substring(0, separatorIndex)] = cookiePart.substring(
        separatorIndex + 1,
      );
    }
    await persistence?.write(cookies);
  }

  String getHeaderValue() {
    if (cookies.isEmpty) return '';
    return cookies.entries
        .map((entry) => '${entry.key}=${entry.value}')
        .join('; ');
  }

  String? get csrfToken => cookies['csrf_token'];

  Future<void> clear() async {
    cookies.clear();
    await persistence?.clear();
  }
}

class ApiService {
  ApiService({
    String? baseUrl,
    http.Client? client,
    CookieStore? cookieStore,
    this.requestTimeout = const Duration(seconds: 25),
  }) : _baseUrl = baseUrl ?? 'http://10.0.2.2:8000/api/v1',
       _client = client ?? http.Client(),
       _cookieStore = cookieStore ?? _sharedCookieStore;

  static final CookieStore _sharedCookieStore = CookieStore(
    persistence: SecureCookiePersistence(),
  );
  static Future<void>? _initializing;
  static bool _initialized = false;
  static Future<bool>? _refreshing;
  static final StreamController<void> _sessionExpiredController =
      StreamController<void>.broadcast();

  final String _baseUrl;
  final http.Client _client;
  final CookieStore _cookieStore;
  final Duration requestTimeout;
  bool _customCookieStoreInitialized = false;

  static Stream<void> get sessionExpiredEvents =>
      _sessionExpiredController.stream;

  static Future<void> initialize() async {
    if (_initialized) return;
    final inProgress = _initializing;
    if (inProgress != null) return inProgress;

    final restore = _sharedCookieStore.restore();
    _initializing = restore;
    try {
      await restore;
      _initialized = true;
    } finally {
      _initializing = null;
    }
  }

  Future<void> restoreCookies() => _initializeCookieStore();

  Future<void> _initializeCookieStore() async {
    if (identical(_cookieStore, _sharedCookieStore)) {
      await initialize();
      return;
    }
    if (_customCookieStoreInitialized) return;
    await _cookieStore.restore();
    _customCookieStoreInitialized = true;
  }

  Map<String, String> get defaultHeaders => {
    'Content-Type': 'application/json',
    if (_cookieStore.getHeaderValue().isNotEmpty)
      'Cookie': _cookieStore.getHeaderValue(),
    if (_cookieStore.csrfToken != null) 'X-CSRF-Token': _cookieStore.csrfToken!,
  };

  Future<http.Response> post(
    String path, {
    Map<String, dynamic>? body,
    bool retryUnauthorized = true,
  }) {
    return _sendWithSessionRefresh(
      () => _client.post(
        Uri.parse('$_baseUrl$path'),
        headers: defaultHeaders,
        body: body == null ? null : jsonEncode(body),
      ),
      retryUnauthorized: retryUnauthorized,
    );
  }

  Future<http.Response> get(String path, {bool retryUnauthorized = true}) {
    return _sendWithSessionRefresh(
      () => _client.get(Uri.parse('$_baseUrl$path'), headers: defaultHeaders),
      retryUnauthorized: retryUnauthorized,
    );
  }

  Future<http.Response> put(
    String path, {
    Map<String, dynamic>? body,
    bool retryUnauthorized = true,
  }) {
    return _sendWithSessionRefresh(
      () => _client.put(
        Uri.parse('$_baseUrl$path'),
        headers: defaultHeaders,
        body: body == null ? null : jsonEncode(body),
      ),
      retryUnauthorized: retryUnauthorized,
    );
  }

  Future<http.Response> patch(
    String path, {
    Map<String, dynamic>? body,
    bool retryUnauthorized = true,
  }) {
    return _sendWithSessionRefresh(
      () => _client.patch(
        Uri.parse('$_baseUrl$path'),
        headers: defaultHeaders,
        body: body == null ? null : jsonEncode(body),
      ),
      retryUnauthorized: retryUnauthorized,
    );
  }

  Future<http.Response> postMultipart(
    String path, {
    required Map<String, String> fields,
    required String fileField,
    required String filename,
    required Uint8List bytes,
    required String contentType,
    bool retryUnauthorized = true,
  }) {
    return _sendWithSessionRefresh(() async {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$_baseUrl$path'),
      );
      request.headers.addAll({
        if (_cookieStore.getHeaderValue().isNotEmpty)
          'Cookie': _cookieStore.getHeaderValue(),
        if (_cookieStore.csrfToken != null)
          'X-CSRF-Token': _cookieStore.csrfToken!,
      });
      request.fields.addAll(fields);
      request.files.add(
        http.MultipartFile.fromBytes(
          fileField,
          bytes,
          filename: filename,
          contentType: MediaType.parse(contentType),
        ),
      );
      return http.Response.fromStream(await _client.send(request));
    }, retryUnauthorized: retryUnauthorized);
  }

  Future<http.Response> _sendWithSessionRefresh(
    Future<http.Response> Function() send, {
    required bool retryUnauthorized,
  }) async {
    try {
      await _initializeCookieStore();
    } catch (_) {
      throw const ApiException(
        'Secure session data could not be opened. Please sign in again.',
      );
    }
    var response = await _sendSafely(send);
    await _updateCookiesSafely(response);
    if (!retryUnauthorized || response.statusCode != 401) return response;

    if (!await _refreshSession()) return response;

    response = await _sendSafely(send);
    await _updateCookiesSafely(response);
    if (response.statusCode == 401) await _expireSession();
    return response;
  }

  Future<bool> _refreshSession() {
    final pending = _refreshing;
    if (pending != null) return pending;

    late final Future<bool> operation;
    operation = _performSessionRefresh().whenComplete(() {
      if (identical(_refreshing, operation)) _refreshing = null;
    });
    _refreshing = operation;
    return operation;
  }

  Future<bool> _performSessionRefresh() async {
    final response = await _sendSafely(
      () => _client.post(
        Uri.parse('$_baseUrl/auth/refresh'),
        headers: defaultHeaders,
      ),
    );
    await _updateCookiesSafely(response);
    if (response.statusCode == 204) return true;
    if (response.statusCode == 401 || response.statusCode == 403) {
      await _expireSession();
    }
    return false;
  }

  Future<void> _expireSession() async {
    try {
      await _cookieStore.clear();
    } finally {
      _sessionExpiredController.add(null);
    }
  }

  Future<void> clearCookies() => _cookieStore.clear();

  Future<void> _updateCookiesSafely(http.Response response) async {
    try {
      await _cookieStore.updateFromResponse(response);
    } catch (_) {
      // The in-memory cookie store is already updated. A device keystore
      // failure must not turn a valid endpoint response into an app crash.
    }
  }

  Future<http.Response> _sendSafely(
    Future<http.Response> Function() send,
  ) async {
    try {
      return await send().timeout(requestTimeout);
    } on TimeoutException {
      throw const ApiException(
        'The request timed out. Check your connection and try again.',
      );
    } on SocketException {
      throw const ApiException(
        'Unable to reach the server. Check your connection and try again.',
      );
    } on http.ClientException {
      throw const ApiException(
        'Unable to reach the server. Check your connection and try again.',
      );
    }
  }
}

class ApiException implements Exception {
  const ApiException(this.message);

  final String message;

  @override
  String toString() => message;
}
