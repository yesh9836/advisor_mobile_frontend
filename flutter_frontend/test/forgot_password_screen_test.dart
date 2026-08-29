import 'package:flutter/material.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/screens/auth/login_screen.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('opens forgot password with the login email and submits it', (
    tester,
  ) async {
    final repository = _FakeAuthRepository();
    await tester.pumpWidget(
      MaterialApp(home: LoginScreen(authRepository: repository)),
    );

    final emailField = find.byType(TextFormField).first;
    await tester.enterText(emailField, 'advisor@example.com');
    await tester.tap(find.text('Forgot password?'));
    await tester.pumpAndSettle();

    expect(find.text('Reset your password'), findsOneWidget);
    expect(find.text('advisor@example.com'), findsOneWidget);

    await tester.tap(find.text('Send reset instructions'));
    await tester.pumpAndSettle();

    expect(repository.requestedEmail, 'advisor@example.com');
    expect(find.text(_genericMessage), findsOneWidget);
  });

  testWidgets('validates the reset email before calling the API', (
    tester,
  ) async {
    final repository = _FakeAuthRepository();
    await tester.pumpWidget(
      MaterialApp(home: LoginScreen(authRepository: repository)),
    );

    await tester.tap(find.text('Forgot password?'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField), 'not-an-email');
    await tester.tap(find.text('Send reset instructions'));
    await tester.pump();

    expect(find.text('Enter a valid email'), findsOneWidget);
    expect(repository.requestedEmail, isNull);
  });
}

const _genericMessage =
    'If an account exists for that email, password reset instructions will be sent.';

class _FakeAuthRepository extends AuthRepository {
  String? requestedEmail;

  @override
  Future<String> requestPasswordReset(String email) async {
    requestedEmail = email;
    return _genericMessage;
  }
}
