import 'dart:convert';
import 'dart:typed_data';
import '../models/auth_models.dart';
import '../services/api_service.dart';

class AuthRepository {
  AuthRepository({ApiService? apiService})
    : _apiService = apiService ?? ApiService();

  final ApiService _apiService;

  Future<UserProfile?> restoreSession() async {
    await _apiService.restoreCookies();
    final currentResponse = await _apiService.get('/auth/me');
    if (currentResponse.statusCode == 200) {
      return UserProfile.fromJson(
        jsonDecode(currentResponse.body) as Map<String, dynamic>,
      );
    }
    if (currentResponse.statusCode != 401) {
      throw AuthException.fromResponse(
        currentResponse.body,
        'Unable to restore your session.',
      );
    }

    final refreshResponse = await _apiService.post('/auth/refresh');
    if (refreshResponse.statusCode == 204) {
      final refreshedUser = await _apiService.get('/auth/me');
      if (refreshedUser.statusCode == 200) {
        return UserProfile.fromJson(
          jsonDecode(refreshedUser.body) as Map<String, dynamic>,
        );
      }
      if (refreshedUser.statusCode == 401 || refreshedUser.statusCode == 403) {
        await _apiService.clearCookies();
        return null;
      }
      throw AuthException.fromResponse(
        refreshedUser.body,
        'Unable to restore your session.',
      );
    }

    if (refreshResponse.statusCode == 401 ||
        refreshResponse.statusCode == 403) {
      await _apiService.clearCookies();
      return null;
    }
    throw AuthException.fromResponse(
      refreshResponse.body,
      'Unable to restore your session.',
    );
  }

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

  Future<AdvisorLicense> submitLicense({
    required String state,
    required String licenseNumber,
    String? licenseType,
    required String filename,
    required Uint8List documentBytes,
    required String contentType,
  }) async {
    final response = await _apiService.postMultipart(
      '/licenses/',
      fields: {
        'state': state.trim().toUpperCase(),
        'license_number': licenseNumber.trim(),
        if (licenseType != null && licenseType.trim().isNotEmpty)
          'license_type': licenseType.trim(),
      },
      fileField: 'document',
      filename: filename,
      bytes: documentBytes,
      contentType: contentType,
    );
    if (response.statusCode != 201) {
      throw AuthException.fromResponse(
        response.body,
        'Unable to submit license.',
      );
    }
    return AdvisorLicense.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
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
    try {
      await _apiService.post('/auth/logout');
    } finally {
      // Always remove encrypted local session data, even if the API is down.
      await _apiService.clearCookies();
    }
  }

  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    final response = await _apiService.post(
      '/auth/change-password',
      body: {'current_password': currentPassword, 'new_password': newPassword},
    );
    if (response.statusCode != 204) {
      throw AuthException.fromResponse(
        response.body,
        'Unable to change password.',
      );
    }
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
