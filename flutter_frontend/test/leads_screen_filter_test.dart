import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/screens/advisor/leads_screen.dart';

void main() {
  testWidgets('opens and applies the Inbox delivery filter', (tester) async {
    final repository = _FilterAdvisorRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: LeadsScreen(repository: repository)),
      ),
    );
    await tester.pumpAndSettle();

    expect(repository.deliveryStatuses, ['all']);
    expect(find.text('1'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('inbox-filter-button')));
    await tester.pumpAndSettle();

    expect(find.text('Filter leads'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('delivery-filter-delivered')));
    await tester.pumpAndSettle();

    expect(repository.deliveryStatuses, ['all', 'delivered']);
    expect(find.text('Filter leads'), findsNothing);
  });
}

class _FilterAdvisorRepository extends AdvisorRepository {
  final List<String> deliveryStatuses = [];

  @override
  Future<List<AdvisorLead>> getLeads({
    String deliveryStatus = 'all',
    String outcomeStatus = 'all',
    String? search,
  }) async {
    deliveryStatuses.add(deliveryStatus);
    return [
      AdvisorLead(
        id: 1,
        stateCode: 'CA',
        firstName: 'Test',
        lastName: 'Lead',
        outcomeStatus: 'new',
        isDownloaded: deliveryStatus == 'delivered',
      ),
    ];
  }
}
