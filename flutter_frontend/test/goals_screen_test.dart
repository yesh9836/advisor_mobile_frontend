import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/screens/advisor/goals_screen.dart';

void main() {
  testWidgets('saves an edited monthly goal and refreshes goal metrics', (
    tester,
  ) async {
    final repository = _FakeAdvisorRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GoalsScreen(repository: repository, onSeeAllPackages: () {}),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Deals Remaining'), findsOneWidget);
    expect(find.text('Closed YTD'), findsOneWidget);
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
    expect(find.text('Behind pace'), findsOneWidget);
    expect(find.text('7 Days'), findsOneWidget);
    expect(find.text('Month'), findsOneWidget);
    expect(find.text('Year'), findsOneWidget);
    expect(find.text('Demo trend data for visualization'), findsOneWidget);
    final sevenDayToggle = find.byKey(const ValueKey('trend-range-sevenDays'));
    await tester.ensureVisible(sevenDayToggle);
    await tester.pumpAndSettle();
    await tester.tap(sevenDayToggle);
    await tester.pumpAndSettle();
    expect(find.text('Required in 7 days'), findsOneWidget);
    expect(find.text('Demo earnings'), findsOneWidget);
    final trendInteraction = find.byKey(
      const ValueKey('goal-trend-interaction'),
    );
    await tester.tapAt(tester.getCenter(trendInteraction));
    await tester.pump();
    expect(
      find.bySemanticsLabel(RegExp(r'Selected .* earnings')),
      findsOneWidget,
    );
    expect(find.text('12 leads recommended per month'), findsOneWidget);

    final monthlyGoalField = find.byType(TextField);
    await tester.ensureVisible(monthlyGoalField);
    final title = find.text('Adjust Monthly Goal');
    final buttonBox = find.byKey(
      const ValueKey('monthly-goal-save-button-box'),
    );
    final titleSizeBeforeEditing = tester.getSize(title);
    final buttonSizeBeforeEditing = tester.getSize(buttonBox);

    await tester.enterText(monthlyGoalField, '2500');
    await tester.pump();

    expect(tester.getSize(title), titleSizeBeforeEditing);
    expect(tester.getSize(buttonBox), buttonSizeBeforeEditing);

    await tester.tap(find.widgetWithText(FilledButton, 'Save'));
    await tester.pumpAndSettle();

    expect(repository.savedMonthlyGoalCents, 250000);
    expect(repository.savedCurrentGoal, same(repository.initialGoal));
    expect(find.text('Goal saved.'), findsOneWidget);
    expect(tester.widget<TextField>(monthlyGoalField).controller?.text, '2500');
  });

  testWidgets('rejects an invalid monthly goal without calling the API', (
    tester,
  ) async {
    final repository = _FakeAdvisorRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GoalsScreen(repository: repository, onSeeAllPackages: () {}),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.drag(find.byType(ListView).first, const Offset(0, -600));
    await tester.pumpAndSettle();

    final monthlyGoalField = find.byType(TextField);
    await tester.ensureVisible(monthlyGoalField);
    await tester.enterText(monthlyGoalField, '0');
    await tester.tap(find.widgetWithText(FilledButton, 'Save'));
    await tester.pump();

    expect(
      find.text('Enter a monthly goal greater than zero.'),
      findsOneWidget,
    );
    expect(repository.savedMonthlyGoalCents, isNull);
  });
}

class _FakeAdvisorRepository extends AdvisorRepository {
  _FakeAdvisorRepository() : initialGoal = _goal(annualGoalCents: 1200000);

  final GoalSnapshot initialGoal;
  GoalSnapshot? savedCurrentGoal;
  int? savedMonthlyGoalCents;

  @override
  Future<GoalSnapshot> getGoal() async => initialGoal;

  @override
  Future<GoalSnapshot> saveMonthlyGoal({
    required GoalSnapshot currentGoal,
    required int monthlyGoalCents,
  }) async {
    savedCurrentGoal = currentGoal;
    savedMonthlyGoalCents = monthlyGoalCents;
    return _goal(annualGoalCents: monthlyGoalCents * 12);
  }
}

GoalSnapshot _goal({required int annualGoalCents}) {
  return GoalSnapshot(
    targetYear: 2026,
    earnedYtdCents: 300000,
    annualGoalCents: annualGoalCents,
    averageCommissionCents: 500000,
    appointmentToDealRateBps: 2500,
    leadToAppointmentRateBps: 1000,
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
    currentSuccessRateBps: 2500,
    recommendedMonthlyLeads: 12,
    pacingStatus: 'behind',
    pacingMessage: 'Increase your monthly lead pace.',
    packages: const [],
  );
}
