import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/models/onboarding_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/screens/advisor/subscription_screen.dart';

void main() {
  testWidgets('saves selected package and target states before checkout', (
    tester,
  ) async {
    final repository = _FakeAdvisorRepository();
    Uri? launchedUrl;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SubscriptionScreen(
            repository: repository,
            checkoutUrlLauncher: (url) async {
              launchedUrl = url;
              return true;
            },
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Continue to checkout'), findsNothing);
    await tester.tap(find.text('Starter'));
    await tester.pumpAndSettle();
    expect(find.text('Continue to checkout'), findsOneWidget);
    await tester.tap(find.text('CA'));
    await tester.tap(find.text('Continue to checkout'));
    await tester.pumpAndSettle();

    expect(repository.savedPackageId, 7);
    expect(repository.savedTargetStates, ['CA']);
    expect(repository.savedRetryToken, startsWith('mobile:7:'));
    expect(launchedUrl, Uri.parse('https://checkout.example/session'));
    expect(find.textContaining('Checkout opened securely'), findsOneWidget);
  });

  testWidgets('enforces the selected package state limit', (tester) async {
    final repository = _FakeAdvisorRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SubscriptionScreen(
            repository: repository,
            checkoutUrlLauncher: (_) async => true,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Starter'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('CA'));
    await tester.tap(find.text('TX'));
    await tester.tap(find.text('Continue to checkout'));
    await tester.pumpAndSettle();

    expect(
      find.textContaining('supports up to 1 target states'),
      findsOneWidget,
    );
    expect(repository.savedPackageId, isNull);
  });

  testWidgets('demo checkout completes without launching an external URL', (
    tester,
  ) async {
    final repository = _FakeAdvisorRepository()..demoMode = true;
    var launcherCalled = false;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SubscriptionScreen(
            repository: repository,
            checkoutUrlLauncher: (_) async {
              launcherCalled = true;
              return true;
            },
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Starter'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('TX'));
    await tester.tap(find.text('Continue to checkout'));
    await tester.pumpAndSettle();

    expect(launcherCalled, isFalse);
    expect(
      find.textContaining('Purchase complete. 10 lead credits were added'),
      findsOneWidget,
    );
  });

  testWidgets('confirms a completed Stripe checkout and reports lead credits', (
    tester,
  ) async {
    final repository = _FakeAdvisorRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SubscriptionScreen(
            repository: repository,
            checkoutUrlLauncher: (_) async => true,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Starter'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('TX'));
    await tester.tap(find.text('Continue to checkout'));
    await tester.pump();
    await tester.tap(find.text('Check purchase status'));
    await tester.pumpAndSettle();

    expect(
      find.textContaining('Purchase complete. 10 lead credits were added'),
      findsOneWidget,
    );
  });
}

class _FakeAdvisorRepository extends AdvisorRepository {
  int? savedPackageId;
  List<String>? savedTargetStates;
  String? savedRetryToken;
  bool demoMode = false;

  @override
  Future<AdvisorOnboarding> getOnboarding() async => const AdvisorOnboarding(
    complete: true,
    consentAccepted: true,
    annualIncomeGoalCents: 25000000,
    averageSaleCents: 2500000,
    commissionRateBps: 2000,
    closingRateBps: 3300,
    leadToAppointmentRateBps: 3333,
    averageCommissionCents: 500000,
    dealsNeeded: 50,
    appointmentsNeeded: 152,
    leadsNeeded: 457,
    licenseStatus: 'verified',
    licenses: [],
  );

  @override
  Future<List<LeadPackage>> getPackages() async => [
    LeadPackage(
      id: 7,
      name: 'Starter',
      priceCents: 10000,
      creditsTotal: 10,
      stateLimit: 1,
    ),
  ];

  @override
  Future<LeadDashboardSummary> getDashboardSummary() async =>
      LeadDashboardSummary(
        leadsDelivered7Days: 0,
        appointmentsSet7Days: 0,
        costPerAppointment: 0,
        currency: 'USD',
        targetStates: const ['CA', 'TX'],
        emailAlertsEnabled: false,
        smsAlertsEnabled: false,
      );

  @override
  Future<PurchaseCheckoutSession> createPurchaseCheckout({
    required int packageId,
    required List<String> targetStates,
    String? retryToken,
  }) async {
    savedPackageId = packageId;
    savedTargetStates = targetStates;
    savedRetryToken = retryToken;
    return PurchaseCheckoutSession(
      sessionId: 'cs_test',
      url: Uri.parse('https://checkout.example/session'),
      demoMode: demoMode,
    );
  }

  @override
  Future<LeadPurchaseStatus?> getPurchaseByCheckoutSession(
    String checkoutSessionId,
  ) async {
    return LeadPurchaseStatus(
      id: 12,
      status: 'completed',
      checkoutSessionId: checkoutSessionId,
      creditsTotal: 10,
      creditsRemaining: 10,
      packageName: 'Starter',
    );
  }
}
