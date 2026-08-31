import 'package:flutter/material.dart';
import 'package:flutter_frontend/models/auth_models.dart';
import 'package:flutter_frontend/models/onboarding_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/screens/advisor/onboarding_screen.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets(
    'mandatory onboarding captures plan and completes with pending license',
    (tester) async {
      final repository = _FakeOnboardingRepository();
      AdvisorOnboarding? completed;

      await tester.pumpWidget(
        MaterialApp(
          home: AdvisorOnboardingScreen(
            mandatory: true,
            initialData: _pendingOnboarding,
            advisorRepository: repository,
            onCompleted: (value) => completed = value,
          ),
        ),
      );

      expect(find.text('Let’s design your income'), findsOneWidget);
      await tester.tap(find.text('Start my plan'));
      await tester.pumpAndSettle();
      expect(
        find.text('What is your desired NET yearly income?'),
        findsOneWidget,
      );

      for (var index = 0; index < 4; index++) {
        await tester.tap(find.text('Next'));
        await tester.pumpAndSettle();
      }

      expect(find.text('Your plan is ready'), findsOneWidget);
      expect(find.text('License in review'), findsOneWidget);
      await tester.tap(find.text('Verification consent'));
      await tester.pump();
      await tester.ensureVisible(find.text('Continue to Buy Leads'));
      await tester.tap(find.text('Continue to Buy Leads'));
      await tester.pumpAndSettle();

      expect(repository.savedIncomeCents, 25000000);
      expect(repository.savedAverageSaleCents, 2500000);
      expect(repository.savedCommissionRateBps, 2000);
      expect(repository.savedClosingRateBps, 3300);
      expect(completed?.complete, isTrue);
    },
  );

  testWidgets('rejected license shows reason and blocks completion', (
    tester,
  ) async {
    final rejected = AdvisorOnboarding(
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
      licenseStatus: 'rejected',
      licenses: [
        AdvisorLicense(
          id: 4,
          state: 'TX',
          licenseNumber: 'TX-123',
          verificationStatus: 'rejected',
          rejectionReason: 'Document is unreadable',
        ),
      ],
    );

    await tester.pumpWidget(
      MaterialApp(
        home: AdvisorOnboardingScreen(
          mandatory: false,
          initialData: rejected,
          advisorRepository: _FakeOnboardingRepository(),
          onCompleted: (_) {},
        ),
      ),
    );
    await tester.tap(find.text('Start my plan'));
    for (var index = 0; index < 4; index++) {
      await tester.pumpAndSettle();
      await tester.tap(find.text('Next'));
    }
    await tester.pumpAndSettle();

    expect(find.text('License needs attention'), findsOneWidget);
    expect(find.text('Document is unreadable'), findsOneWidget);
    expect(find.text('Resubmit'), findsOneWidget);
  });
}

const _pendingOnboarding = AdvisorOnboarding(
  complete: false,
  consentAccepted: false,
  annualIncomeGoalCents: 25000000,
  averageSaleCents: 2500000,
  commissionRateBps: 2000,
  closingRateBps: 3300,
  leadToAppointmentRateBps: 3333,
  averageCommissionCents: 500000,
  dealsNeeded: 50,
  appointmentsNeeded: 152,
  leadsNeeded: 457,
  licenseStatus: 'pending',
  licenses: [],
);

class _FakeOnboardingRepository extends AdvisorRepository {
  int? savedIncomeCents;
  int? savedAverageSaleCents;
  int? savedCommissionRateBps;
  int? savedClosingRateBps;

  @override
  Future<AdvisorOnboarding> getOnboarding() async => _pendingOnboarding;

  @override
  Future<AdvisorOnboarding> saveOnboarding({
    required int annualIncomeGoalCents,
    required int averageSaleCents,
    required int commissionRateBps,
    required int closingRateBps,
    required bool consentAccepted,
  }) async {
    savedIncomeCents = annualIncomeGoalCents;
    savedAverageSaleCents = averageSaleCents;
    savedCommissionRateBps = commissionRateBps;
    savedClosingRateBps = closingRateBps;
    return const AdvisorOnboarding(
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
      licenseStatus: 'pending',
      licenses: [],
    );
  }
}
