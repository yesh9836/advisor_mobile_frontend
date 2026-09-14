import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/screens/advisor/goals_screen.dart';

void main() {
  testWidgets('refreshes conversion success after a lead outcome changes', (
    tester,
  ) async {
    final revision = ValueNotifier<int>(0);
    addTearDown(revision.dispose);
    final repository = _RefreshingGoalRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GoalsScreen(
            repository: repository,
            outcomeRevision: revision,
            onSeeAllPackages: (_) {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('20%'), findsOneWidget);
    revision.value++;
    await tester.pumpAndSettle();

    expect(find.text('50%'), findsOneWidget);
    expect(repository.loadCount, 2);
  });

  testWidgets('saves an edited monthly goal and refreshes goal metrics', (
    tester,
  ) async {
    final repository = _FakeAdvisorRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GoalsScreen(repository: repository, onSeeAllPackages: (_) {}),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Deals closed'), findsOneWidget);
    expect(find.text('Appointments set'), findsOneWidget);
    expect(find.text('Leads contacted'), findsOneWidget);
    expect(find.text('Est. commission'), findsOneWidget);
    await tester.tap(find.text('Deals closed'));
    await tester.pumpAndSettle();
    expect(find.text('Closed deals since joining'), findsOneWidget);
    expect(find.text('Calculation'), findsOneWidget);
    expect(find.text('Test Closed Lead'), findsOneWidget);
    await tester.tap(find.text('Test Closed Lead'));
    await tester.pumpAndSettle();
    expect(find.text('Lead Details'), findsOneWidget);
    Navigator.of(tester.element(find.text('Lead Details'))).pop();
    await tester.pumpAndSettle();
    expect(find.text('Conversion success'), findsOneWidget);
    expect(find.text('SET SUCCESS RATE'), findsOneWidget);
    expect(find.text('CURRENT SUCCESS RATE'), findsOneWidget);
    expect(find.text('25%'), findsNWidgets(2));
    expect(
      find.text('10 contacted • 2 appointment set • 4 closed'),
      findsOneWidget,
    );
    await tester.drag(find.byType(ListView).first, const Offset(0, -600));
    await tester.pumpAndSettle();

    expect(find.text('Income trend'), findsOneWidget);
    expect(
      find.text(
        'Current-year performance • based on actual closed-deal updates',
      ),
      findsOneWidget,
    );
    expect(find.text('Actual history'), findsOneWidget);
    expect(find.text('Goal pace'), findsOneWidget);
    expect(find.byKey(const ValueKey('goal-activity-trend')), findsOneWidget);
    await tester.drag(find.byType(ListView).first, const Offset(0, -280));
    await tester.pumpAndSettle();
    expect(find.text('12 leads recommended per month'), findsOneWidget);

    await tester.drag(find.byType(ListView).first, const Offset(0, 1400));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('monthly-goal-adjust-button')));
    await tester.pumpAndSettle();
    final monthlyGoalField = find.byType(TextField);
    await tester.ensureVisible(monthlyGoalField);
    final title = find.text('Monthly goal');
    final buttonBox = find.byKey(
      const ValueKey('monthly-goal-save-button-box'),
    );
    final titleSizeBeforeEditing = tester.getSize(title);
    final buttonSizeBeforeEditing = tester.getSize(buttonBox);

    await tester.enterText(monthlyGoalField, '2500');
    await tester.pump();

    expect(tester.getSize(title), titleSizeBeforeEditing);
    expect(tester.getSize(buttonBox), buttonSizeBeforeEditing);

    final saveButton = find.widgetWithText(FilledButton, 'Save');
    await tester.ensureVisible(saveButton);
    await tester.pumpAndSettle();
    await tester.tap(saveButton);
    await tester.pumpAndSettle();

    expect(repository.savedMonthlyGoalCents, 250000);
    expect(repository.savedCurrentGoal, same(repository.initialGoal));
    expect(
      find.byKey(const ValueKey('monthly-goal-adjust-button')),
      findsOneWidget,
    );
    expect(find.text(r'$2,500'), findsOneWidget);
  });

  testWidgets('rejects an invalid monthly goal without calling the API', (
    tester,
  ) async {
    final repository = _FakeAdvisorRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GoalsScreen(repository: repository, onSeeAllPackages: (_) {}),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final adjustButton = find.byKey(
      const ValueKey('monthly-goal-adjust-button'),
    );
    await tester.ensureVisible(adjustButton);
    await tester.pumpAndSettle();
    await tester.tap(adjustButton);
    await tester.pumpAndSettle();
    final monthlyGoalField = find.byType(TextField);
    await tester.ensureVisible(monthlyGoalField);
    await tester.enterText(monthlyGoalField, '0');
    final saveButton = find.widgetWithText(FilledButton, 'Save');
    await tester.ensureVisible(saveButton);
    await tester.pumpAndSettle();
    await tester.tap(saveButton);
    await tester.pump();

    expect(
      find.text('Enter a monthly goal greater than zero.'),
      findsOneWidget,
    );
    expect(repository.savedMonthlyGoalCents, isNull);
  });

  testWidgets('shows and updates the goal funnel assumptions', (tester) async {
    final repository = _FakeAdvisorRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GoalsScreen(repository: repository, onSeeAllPackages: (_) {}),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.drag(find.byType(ListView).first, const Offset(0, -500));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Your funnel'));
    await tester.pumpAndSettle();
    expect(find.text('Your funnel'), findsOneWidget);
    expect(find.text('400'), findsOneWidget);
    expect(find.text('40'), findsOneWidget);
    expect(find.text('10'), findsWidgets);

    await tester.tap(find.byKey(const ValueKey('edit-funnel-button')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const ValueKey('funnel-commission-field')),
      '7500',
    );
    await tester.enterText(
      find.byKey(const ValueKey('funnel-appointment-rate-field')),
      '30',
    );
    await tester.enterText(
      find.byKey(const ValueKey('funnel-lead-rate-field')),
      '15',
    );
    await tester.tap(find.byKey(const ValueKey('save-funnel-button')));
    await tester.pumpAndSettle();

    expect(repository.savedAverageCommissionCents, 750000);
    expect(repository.savedAppointmentRateBps, 3000);
    expect(repository.savedLeadRateBps, 1500);
    expect(find.text('Funnel assumptions updated.'), findsOneWidget);
  });

  testWidgets('switches stats and graph to the registration period', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GoalsScreen(
            repository: _FakeAdvisorRepository(),
            onSeeAllPackages: (_) {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.drag(find.byType(ListView).first, const Offset(0, -600));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Since joining'));
    await tester.pumpAndSettle();

    expect(find.text('25%'), findsNWidgets(2));
    expect(
      find.text(
        'Complete history since joining • based on actual closed-deal updates',
      ),
      findsOneWidget,
    );
  });
}

class _FakeAdvisorRepository extends AdvisorRepository {
  _FakeAdvisorRepository() : initialGoal = _goal(annualGoalCents: 1200000);

  final GoalSnapshot initialGoal;
  GoalSnapshot? savedCurrentGoal;
  int? savedMonthlyGoalCents;
  int? savedAverageCommissionCents;
  int? savedAppointmentRateBps;
  int? savedLeadRateBps;

  @override
  Future<GoalSnapshot> getGoal() async => initialGoal;

  @override
  Future<List<AdvisorLead>> getLeads({
    String deliveryStatus = 'all',
    String outcomeStatus = 'all',
    String? search,
  }) async => [
    AdvisorLead(
      id: 1,
      firstName: 'Test',
      lastName: 'Closed Lead',
      stateCode: 'CA',
      outcomeStatus: outcomeStatus == 'all' ? 'contacted' : outcomeStatus,
      outcomeUpdatedAt: DateTime(2026, 6, 1),
      piiUnlocked: true,
      isDownloaded: true,
    ),
  ];

  @override
  Future<AdvisorLeadPage> getLeadsPage({
    int page = 1,
    int size = 20,
    String deliveryStatus = 'all',
    String outcomeStatus = 'all',
    String? search,
  }) async {
    final items = await getLeads(
      deliveryStatus: deliveryStatus,
      outcomeStatus: outcomeStatus,
      search: search,
    );
    return AdvisorLeadPage(
      items: items,
      total: items.length,
      page: page,
      size: size,
    );
  }

  @override
  Future<GoalSnapshot> saveMonthlyGoal({
    required GoalSnapshot currentGoal,
    required int monthlyGoalCents,
  }) async {
    savedCurrentGoal = currentGoal;
    savedMonthlyGoalCents = monthlyGoalCents;
    return _goal(annualGoalCents: monthlyGoalCents * 12);
  }

  @override
  Future<GoalSnapshot> saveGoalFunnel({
    required GoalSnapshot currentGoal,
    required int averageCommissionCents,
    required int appointmentToDealRateBps,
    required int leadToAppointmentRateBps,
  }) async {
    savedAverageCommissionCents = averageCommissionCents;
    savedAppointmentRateBps = appointmentToDealRateBps;
    savedLeadRateBps = leadToAppointmentRateBps;
    return _goal(
      annualGoalCents: currentGoal.annualGoalCents,
      averageCommissionCents: averageCommissionCents,
      appointmentToDealRateBps: appointmentToDealRateBps,
      leadToAppointmentRateBps: leadToAppointmentRateBps,
    );
  }
}

class _RefreshingGoalRepository extends AdvisorRepository {
  int loadCount = 0;

  @override
  Future<GoalSnapshot> getGoal() async {
    loadCount++;
    return _goal(
      annualGoalCents: 1200000,
      currentSuccessRateBps: loadCount == 1 ? 2000 : 5000,
    );
  }
}

GoalSnapshot _goal({
  required int annualGoalCents,
  int currentSuccessRateBps = 2500,
  int averageCommissionCents = 500000,
  int appointmentToDealRateBps = 2500,
  int leadToAppointmentRateBps = 1000,
}) {
  return GoalSnapshot(
    targetYear: 2026,
    earnedYtdCents: 300000,
    annualGoalCents: annualGoalCents,
    averageCommissionCents: averageCommissionCents,
    appointmentToDealRateBps: appointmentToDealRateBps,
    leadToAppointmentRateBps: leadToAppointmentRateBps,
    incomeProgressPercent: 25,
    appointmentsNeeded: 40,
    dealsNeeded: 10,
    leadsNeeded: 400,
    appointmentsRemaining: 24,
    dealsRemaining: 6,
    leadsRemaining: 240,
    closedDealsYtd: 4,
    contactedLeadsYtd: 10,
    appointmentsSetYtd: 2,
    reachedLeadsYtd: 16,
    currentSuccessRateBps: currentSuccessRateBps,
    recommendedMonthlyLeads: 12,
    pacingStatus: 'behind',
    pacingMessage: 'Increase your monthly lead pace.',
    registeredAt: DateTime(2026, 3, 12),
    calendarActivity: GoalActivitySummary(
      contacted: 10,
      appointmentsSet: 2,
      closedDeals: 4,
      reachedLeads: 16,
      successRateBps: currentSuccessRateBps,
      estimatedEarningsCents: 2000000,
    ),
    sinceRegistrationActivity: GoalActivitySummary(
      contacted: 10,
      appointmentsSet: 2,
      closedDeals: 4,
      reachedLeads: 16,
      successRateBps: currentSuccessRateBps,
      estimatedEarningsCents: 2000000,
    ),
    calendarMonthlyActivity: const [
      GoalMonthlyActivityPoint(year: 2026, month: 1, label: 'Jan 2026'),
      GoalMonthlyActivityPoint(
        year: 2026,
        month: 2,
        label: 'Feb 2026',
        closedDeals: 4,
        estimatedEarningsCents: 2000000,
      ),
    ],
    sinceRegistrationMonthlyActivity: const [
      GoalMonthlyActivityPoint(
        year: 2026,
        month: 3,
        label: 'Mar 2026',
        closedDeals: 4,
        estimatedEarningsCents: 2000000,
      ),
    ],
    packages: const [],
  );
}
