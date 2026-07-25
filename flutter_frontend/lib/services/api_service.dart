import 'dart:convert';
import 'package:http/http.dart' as http;

class CookieStore {
  final Map<String, String> cookies = {};

  void updateFromResponse(http.Response response) {
    final rawSetCookie = response.headers['set-cookie'];
    if (rawSetCookie == null || rawSetCookie.isEmpty) return;

    final cookieDefinitions = rawSetCookie.split(RegExp(r', (?=[^;,]+=)'));
    for (final definition in cookieDefinitions) {
      final cookiePart = definition.split(';').first.trim();
      final separatorIndex = cookiePart.indexOf('=');
      if (separatorIndex < 0) continue;
      cookies[cookiePart.substring(0, separatorIndex)] = cookiePart.substring(
        separatorIndex + 1,
      );
    }
  }

  String getHeaderValue() {
    if (cookies.isEmpty) return '';
    return cookies.entries
        .map((entry) => '${entry.key}=${entry.value}')
        .join('; ');
  }

  String? get csrfToken => cookies['csrf_token'];

  void clear() => cookies.clear();
}

class ApiService {
  ApiService({String? baseUrl})
    : _baseUrl = baseUrl ?? 'http://10.0.2.2:8000/api/v1';

  static final CookieStore _sharedCookieStore = CookieStore();

  final String _baseUrl;
  CookieStore get _cookieStore => _sharedCookieStore;

  Map<String, String> get defaultHeaders => {
    'Content-Type': 'application/json',
    if (_cookieStore.getHeaderValue().isNotEmpty)
      'Cookie': _cookieStore.getHeaderValue(),
    if (_cookieStore.csrfToken != null) 'X-CSRF-Token': _cookieStore.csrfToken!,
  };

  Future<http.Response> post(String path, {Map<String, dynamic>? body}) async {
    final response = await http.post(
      Uri.parse('$_baseUrl$path'),
      headers: defaultHeaders,
      body: body == null ? null : jsonEncode(body),
    );
    _cookieStore.updateFromResponse(response);
    return response;
  }

  Future<http.Response> get(String path) async {
    final response = await http.get(
      Uri.parse('$_baseUrl$path'),
      headers: defaultHeaders,
    );
    _cookieStore.updateFromResponse(response);
    return response;
  }

  Future<http.Response> put(String path, {Map<String, dynamic>? body}) async {
    final response = await http.put(
      Uri.parse('$_baseUrl$path'),
      headers: defaultHeaders,
      body: body == null ? null : jsonEncode(body),
    );
    _cookieStore.updateFromResponse(response);
    return response;
  }

  void clearCookies() => _cookieStore.clear();
}
