import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/models/auth_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/screens/advisor/advisor_shell.dart';

void main() {
  testWidgets('shows five compact recent leads on Home', (tester) async {
    final repository = _FakeAdvisorRepository(withLeads: true);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AdvisorDashboardScreen(
            repository: repository,
            authRepository: _FakeAuthRepository(),
            onBuyLeads: () {},
            onViewInbox: () {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    for (var index = 1; index <= 5; index++) {
      expect(find.text('Recent Lead $index'), findsOneWidget);
    }
    expect(find.text('Recent Lead 6'), findsNothing);
  });

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
    expect(find.bySemanticsLabel('Email Alerts toggle'), findsOneWidget);
    expect(find.bySemanticsLabel('SMS Alerts toggle'), findsOneWidget);
    expect(find.text('ON'), findsNothing);
    expect(find.text('OFF'), findsNothing);
    await tester.tap(find.bySemanticsLabel('Email Alerts toggle'));
    await tester.pumpAndSettle();

    expect(find.text('ON'), findsNothing);
    expect(find.text('OFF'), findsNothing);
    expect(repository.savedEmailEnabled, isFalse);
    expect(repository.savedSmsEnabled, isTrue);
    expect(repository.savedExpectedVersion, 4);
    expect(find.text('Delivery settings updated.'), findsOneWidget);
  });

  testWidgets('refreshes Home by pulling down without a header button', (
    tester,
  ) async {
    final repository = _FakeAdvisorRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AdvisorDashboardScreen(
            repository: repository,
            authRepository: _FakeAuthRepository(),
            onBuyLeads: () {},
            onViewInbox: () {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.bySemanticsLabel('Refresh Home'), findsNothing);
    expect(find.byType(RefreshIndicator), findsOneWidget);
    expect(repository.dashboardRequests, 1);

    await tester.drag(find.byType(ListView), const Offset(0, 320));
    await tester.pumpAndSettle();

    expect(repository.dashboardRequests, 2);
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
  _FakeAdvisorRepository({this.withLeads = false});

  final bool withLeads;
  bool? savedEmailEnabled;
  bool? savedSmsEnabled;
  int? savedExpectedVersion;
  int dashboardRequests = 0;

  @override
  Future<LeadDashboardSummary> getDashboardSummary() async {
    dashboardRequests++;
    return LeadDashboardSummary(
      leadsDelivered7Days: 9,
      appointmentsSet7Days: 2,
      costPerAppointment: 100,
      currency: 'USD',
      targetStates: const ['CA'],
      emailAlertsEnabled: true,
      smsAlertsEnabled: true,
    );
  }

  @override
  Future<List<AdvisorLead>> getLeads({
    String deliveryStatus = 'all',
    String outcomeStatus = 'all',
    String? search,
  }) async => withLeads
      ? List.generate(
          6,
          (index) => AdvisorLead(
            id: index + 1,
            stateCode: 'CA',
            firstName: 'Recent',
            lastName: 'Lead ${index + 1}',
            assets: r'$100k-$250k',
            activity: 'Travel',
            outcomeStatus: 'new',
            receivedAt: DateTime(2026, 9, 1),
          ),
        )
      : const [];

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
