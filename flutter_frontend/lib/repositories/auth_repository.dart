import 'dart:convert';
import '../models/auth_models.dart';
import '../services/api_service.dart';

class AuthRepository {
  AuthRepository({ApiService? apiService})
    : _apiService = apiService ?? ApiService();

  final ApiService _apiService;

  Future<UserProfile> getCurrentUser() async {
    final response = await _apiService.get('/auth/me');
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(response.body, 'Failed to load user.');
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return UserProfile.fromJson(data);
  }

  Future<List<AdvisorLicense>> getMyLicenses() async {
    final response = await _apiService.get('/licenses/');
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(
        response.body,
        'Failed to load licenses.',
      );
    }

    final data = jsonDecode(response.body) as List;
    return data
        .map((item) => AdvisorLicense.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<void> login(LoginRequest request) async {
    final response = await _apiService.post(
      '/auth/login',
      body: request.toJson(),
    );
    if (response.statusCode != 204) {
      throw AuthException.fromResponse(response.body, 'Login failed.');
    }
  }

  Future<UserProfile> register(RegisterRequest request) async {
    final response = await _apiService.post(
      '/auth/register',
      body: request.toJson(),
    );
    if (response.statusCode != 201) {
      throw AuthException.fromResponse(response.body, 'Registration failed.');
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return UserProfile.fromJson(data);
  }

  Future<void> registerAndLogin(RegisterRequest request) async {
    await register(request);
    await login(LoginRequest(email: request.email, password: request.password));
  }

  Future<void> logout() async {
    await _apiService.post('/auth/logout');
    // Clear any client-side cookies after logging out.
    _apiService.clearCookies();
  }
}

class AuthException implements Exception {
  AuthException(this.message);

  final String message;

  factory AuthException.fromResponse(String body, String fallback) {
    try {
      final data = jsonDecode(body) as Map<String, dynamic>;
      final detail = data['detail'];
      if (detail is String && detail.isNotEmpty) {
        return AuthException(detail);
      }
      if (detail is List && detail.isNotEmpty) {
        final first = detail.first;
        if (first is Map<String, dynamic>) {
          final message = first['msg'];
          if (message is String && message.isNotEmpty) {
            return AuthException(message);
          }
        }
      }
    } catch (_) {
      // Fall back when the backend response is empty or not JSON.
    }
    return AuthException(fallback);
  }

  @override
  String toString() => message;
}
