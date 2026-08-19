import 'package:flutter/material.dart';
import 'package:flutter_frontend/main.dart';
import 'package:flutter_frontend/models/auth_models.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('shows advisor login screen', (WidgetTester tester) async {
    await tester.pumpWidget(
      SpectaculeadsApp(authRepository: _SignedOutAuthRepository()),
    );
    await tester.pumpAndSettle();

    expect(find.text('Spectaculeads'), findsOneWidget);
    expect(find.text('Sign In'), findsOneWidget);

    final emailField = find.byType(TextFormField).at(0);
    final passwordField = find.byType(TextFormField).at(1);
    await tester.enterText(emailField, 'advisor.demo@example.com');
    await tester.enterText(passwordField, 'Password123!');

    expect(find.text('advisor.demo@example.com'), findsOneWidget);
    expect(find.text('Password123!'), findsOneWidget);
  });
}

class _SignedOutAuthRepository extends AuthRepository {
  @override
  Future<UserProfile?> restoreSession() async => null;
}
