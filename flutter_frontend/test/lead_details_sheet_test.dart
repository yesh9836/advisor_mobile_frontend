import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/screens/advisor/lead_details_sheet.dart';
import 'package:flutter_frontend/screens/advisor/leads_screen.dart';

void main() {
  testWidgets('opens a lead from Inbox', (tester) async {
    final repository = _FakeLeadRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: LeadsScreen(repository: repository)),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Test Advisor Lead'));
    await tester.pumpAndSettle();

    expect(find.text('Lead Details'), findsOneWidget);
    expect(find.text('555-0100'), findsOneWidget);
    expect(find.text(r'$250k-$500k'), findsWidgets);
  });

  testWidgets('updates status and notes from lead details', (tester) async {
    final repository = _FakeLeadRepository();
    AdvisorLead? callbackLead;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: LeadDetailsSheet(
            lead: repository.lead,
            repository: repository,
            onUpdated: (lead) => callbackLead = lead,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.drag(find.byType(ListView), const Offset(0, -700));
    await tester.pumpAndSettle();

    await tester.tap(find.byType(DropdownButtonFormField<String>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Appointment Set').last);
    await tester.pumpAndSettle();

    await tester.enterText(
      find.widgetWithText(TextField, 'Notes'),
      'Meeting booked for Tuesday.',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Save lead update'));
    await tester.pumpAndSettle();

    expect(repository.savedStatus, 'appointment_set');
    expect(repository.savedNotes, 'Meeting booked for Tuesday.');
    expect(callbackLead?.outcomeStatus, 'appointment_set');
    expect(find.text('Lead update saved.'), findsOneWidget);
  });

  testWidgets('does not offer status updates for a locked lead', (
    tester,
  ) async {
    final repository = _FakeLeadRepository();
    final lockedLead = AdvisorLead(
      id: 9,
      stateCode: 'TX',
      piiUnlocked: false,
      isDownloaded: false,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: LeadDetailsSheet(
            lead: lockedLead,
            repository: repository,
            onUpdated: (_) {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Locked Lead'), findsOneWidget);
    expect(
      find.textContaining('status updates become available'),
      findsOneWidget,
    );
    expect(find.text('Save lead update'), findsNothing);
  });
}

class _FakeLeadRepository extends AdvisorRepository {
  final lead = AdvisorLead(
    id: 7,
    stateCode: 'AZ',
    zipCode: '85001',
    firstName: 'Test',
    lastName: 'Advisor Lead',
    mobilePhone: '555-0100',
    preferredFollowUpMethod: 'Phone',
    bestTimeToReach: 'Morning',
    retirementTimeline: 'Within 5 years',
    assets: r'$250k-$500k',
    activity: 'Retirement income planning',
    annualHouseholdIncomeRange: r'$100k-$150k',
    outcomeStatus: 'contacted',
    outcomeNotes: 'Initial call completed.',
    receivedAt: DateTime(2026, 8, 9),
    piiUnlocked: true,
    isDownloaded: true,
  );

  String? savedStatus;
  String? savedNotes;

  @override
  Future<List<AdvisorLead>> getLeads({
    String deliveryStatus = 'all',
    String outcomeStatus = 'all',
    String? search,
  }) async => [lead];

  @override
  Future<AdvisorLead> updateLeadOutcome({
    required AdvisorLead lead,
    required String status,
    String? notes,
  }) async {
    savedStatus = status;
    savedNotes = notes;
    return lead.copyWithOutcome(status: status, notes: notes);
  }
}
