import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:flutter_frontend/services/api_service.dart';

void main() {
  test('cookie store captures csrf token from set-cookie headers', () {
    final cookieStore = CookieStore();
    final response = http.Response(
      '',
      200,
      headers: {'set-cookie': 'csrf_token=abc123; Path=/; HttpOnly'},
    );

    cookieStore.updateFromResponse(response);

    expect(cookieStore.cookies['csrf_token'], 'abc123');
    expect(cookieStore.getHeaderValue(), 'csrf_token=abc123');
  });
}
