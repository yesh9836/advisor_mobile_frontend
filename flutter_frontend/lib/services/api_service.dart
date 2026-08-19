import 'dart:convert';
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
  ApiService({String? baseUrl})
    : _baseUrl = baseUrl ?? 'http://10.0.2.2:8000/api/v1';

  static final CookieStore _sharedCookieStore = CookieStore(
    persistence: SecureCookiePersistence(),
  );
  static Future<void>? _initializing;
  static bool _initialized = false;

  final String _baseUrl;
  CookieStore get _cookieStore => _sharedCookieStore;

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

  Future<void> restoreCookies() => initialize();

  Map<String, String> get defaultHeaders => {
    'Content-Type': 'application/json',
    if (_cookieStore.getHeaderValue().isNotEmpty)
      'Cookie': _cookieStore.getHeaderValue(),
    if (_cookieStore.csrfToken != null) 'X-CSRF-Token': _cookieStore.csrfToken!,
  };

  Future<http.Response> post(String path, {Map<String, dynamic>? body}) async {
    await initialize();
    final response = await http.post(
      Uri.parse('$_baseUrl$path'),
      headers: defaultHeaders,
      body: body == null ? null : jsonEncode(body),
    );
    await _cookieStore.updateFromResponse(response);
    return response;
  }

  Future<http.Response> get(String path) async {
    await initialize();
    final response = await http.get(
      Uri.parse('$_baseUrl$path'),
      headers: defaultHeaders,
    );
    await _cookieStore.updateFromResponse(response);
    return response;
  }

  Future<http.Response> put(String path, {Map<String, dynamic>? body}) async {
    await initialize();
    final response = await http.put(
      Uri.parse('$_baseUrl$path'),
      headers: defaultHeaders,
      body: body == null ? null : jsonEncode(body),
    );
    await _cookieStore.updateFromResponse(response);
    return response;
  }

  Future<http.Response> patch(String path, {Map<String, dynamic>? body}) async {
    await initialize();
    final response = await http.patch(
      Uri.parse('$_baseUrl$path'),
      headers: defaultHeaders,
      body: body == null ? null : jsonEncode(body),
    );
    await _cookieStore.updateFromResponse(response);
    return response;
  }

  Future<http.Response> postMultipart(
    String path, {
    required Map<String, String> fields,
    required String fileField,
    required String filename,
    required Uint8List bytes,
    required String contentType,
  }) async {
    await initialize();
    final request = http.MultipartRequest('POST', Uri.parse('$_baseUrl$path'));
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
    final streamed = await request.send();
    final response = await http.Response.fromStream(streamed);
    await _cookieStore.updateFromResponse(response);
    return response;
  }

  Future<void> clearCookies() => _cookieStore.clear();
}
