import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/models/auth_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/screens/advisor/advisor_shell.dart';

void main() {
  testWidgets('updates delivery settings from inline toggles', (tester) async {
    final repository = _FakeAdvisorRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AdvisorDashboardScreen(
            repository: repository,
            authRepository: _FakeAuthRepository(),
            onBuyLeads: () {},
            onViewInbox: () {},
            onOpenProfile: () {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.text('Delivery Settings'),
      500,
      scrollable: find.byType(Scrollable).first,
    );

    expect(find.text('Edit'), findsNothing);
    expect(find.byType(Switch), findsNWidgets(2));
    await tester.tap(find.byType(Switch).first);
    await tester.pumpAndSettle();

    expect(repository.savedEmailEnabled, isFalse);
    expect(repository.savedSmsEnabled, isTrue);
    expect(repository.savedExpectedVersion, 4);
    expect(find.text('Delivery settings updated.'), findsOneWidget);
  });
}

class _FakeAuthRepository extends AuthRepository {
  @override
  Future<UserProfile> getCurrentUser() async => UserProfile(
    id: 1,
    email: 'advisor@example.com',
    name: 'Test Advisor',
    role: 'advisor',
  );
}

class _FakeAdvisorRepository extends AdvisorRepository {
  bool? savedEmailEnabled;
  bool? savedSmsEnabled;
  int? savedExpectedVersion;

  @override
  Future<LeadDashboardSummary> getDashboardSummary() async =>
      LeadDashboardSummary(
        leadsDelivered7Days: 9,
        appointmentsSet7Days: 2,
        costPerAppointment: 100,
        currency: 'USD',
        targetStates: const ['CA'],
        emailAlertsEnabled: true,
        smsAlertsEnabled: true,
      );

  @override
  Future<List<AdvisorLead>> getLeads({
    String deliveryStatus = 'all',
    String outcomeStatus = 'all',
    String? search,
  }) async => const [];

  @override
  Future<DeliverySettings> getDeliverySettings() async => DeliverySettings(
    emailAlertsEnabled: true,
    smsAlertsEnabled: true,
    version: 4,
    warnings: const [],
  );

  @override
  Future<DeliverySettings> updateDeliverySettings({
    required bool emailAlertsEnabled,
    required bool smsAlertsEnabled,
    required int expectedVersion,
  }) async {
    savedEmailEnabled = emailAlertsEnabled;
    savedSmsEnabled = smsAlertsEnabled;
    savedExpectedVersion = expectedVersion;
    return DeliverySettings(
      emailAlertsEnabled: emailAlertsEnabled,
      smsAlertsEnabled: smsAlertsEnabled,
      version: expectedVersion + 1,
      warnings: const [],
    );
  }
}
