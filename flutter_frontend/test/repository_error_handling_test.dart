import 'dart:typed_data';

import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'license upload converts malformed success responses to AuthException',
    () {
      final repository = AuthRepository(
        apiService: _apiReturning(
          http.Response('<html>bad gateway</html>', 201),
        ),
      );

      expect(
        repository.submitLicense(
          state: 'TX',
          licenseNumber: 'LIC-123',
          filename: 'license.pdf',
          documentBytes: Uint8List.fromList([1, 2, 3]),
          contentType: 'application/pdf',
        ),
        throwsA(
          isA<AuthException>().having(
            (error) => error.message,
            'message',
            contains('invalid response'),
          ),
        ),
      );
    },
  );

  test('dashboard converts malformed success responses to AuthException', () {
    final repository = AdvisorRepository(
      apiService: _apiReturning(http.Response('[]', 200)),
    );

    expect(repository.getDashboardSummary(), throwsA(isA<AuthException>()));
  });

  test(
    'backend validation details are safe for every non-success endpoint',
    () {
      final repository = AuthRepository(
        apiService: _apiReturning(
          http.Response('{"detail":[{"msg":"Unsupported document"}]}', 422),
        ),
      );

      expect(
        repository.submitLicense(
          state: 'TX',
          licenseNumber: 'LIC-123',
          filename: 'license.pdf',
          documentBytes: Uint8List.fromList([1]),
          contentType: 'application/pdf',
        ),
        throwsA(
          isA<AuthException>().having(
            (error) => error.message,
            'message',
            'Unsupported document',
          ),
        ),
      );
    },
  );
}

ApiService _apiReturning(http.Response response) {
  return ApiService(
    baseUrl: 'https://api.example.test/api/v1',
    client: MockClient((_) async => response),
    cookieStore: CookieStore(),
  );
}
