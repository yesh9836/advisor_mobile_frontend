import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/screens/advisor/leads_screen.dart';

void main() {
  testWidgets('shows the API total and loads another page near the bottom', (
    tester,
  ) async {
    final repository = _FilterAdvisorRepository(total: 45);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: LeadsScreen(repository: repository)),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('45'), findsOneWidget);
    expect(repository.pageRequests, [1]);

    await tester.drag(find.byType(ListView).first, const Offset(0, -2200));
    await tester.pumpAndSettle();

    expect(repository.pageRequests, contains(2));
    expect(find.text('Test 21'), findsOneWidget);
  });

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
    expect(
      find.descendant(
        of: find.byKey(const ValueKey('outcome-filter-all')),
        matching: find.byKey(const ValueKey('selected-filter-count')),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: find.byKey(const ValueKey('outcome-filter-new')),
        matching: find.byKey(const ValueKey('selected-filter-count')),
      ),
      findsNothing,
    );

    await tester.tap(find.byKey(const ValueKey('outcome-filter-new')));
    await tester.pumpAndSettle();

    expect(
      find.descendant(
        of: find.byKey(const ValueKey('outcome-filter-new')),
        matching: find.byKey(const ValueKey('selected-filter-count')),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: find.byKey(const ValueKey('outcome-filter-all')),
        matching: find.byKey(const ValueKey('selected-filter-count')),
      ),
      findsNothing,
    );
    await tester.tap(find.byKey(const ValueKey('inbox-filter-button')));
    await tester.pumpAndSettle();

    expect(find.text('Filter leads'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('delivery-filter-delivered')));
    await tester.pumpAndSettle();

    expect(repository.deliveryStatuses, ['all', 'all', 'delivered']);
    expect(find.text('Filter leads'), findsNothing);
  });
}

class _FilterAdvisorRepository extends AdvisorRepository {
  _FilterAdvisorRepository({this.total = 1});

  final int total;
  final List<String> deliveryStatuses = [];
  final List<int> pageRequests = [];

  @override
  Future<AdvisorLeadPage> getLeadsPage({
    int page = 1,
    int size = 20,
    String deliveryStatus = 'all',
    String outcomeStatus = 'all',
    String? search,
  }) async {
    deliveryStatuses.add(deliveryStatus);
    pageRequests.add(page);
    final firstId = ((page - 1) * size) + 1;
    final count = (total - firstId + 1).clamp(0, size);
    final items = List.generate(
      count,
      (index) => AdvisorLead(
        id: firstId + index,
        stateCode: 'CA',
        firstName: 'Test',
        lastName: '${firstId + index}',
        outcomeStatus: 'new',
        isDownloaded: deliveryStatus == 'delivered',
      ),
    );
    return AdvisorLeadPage(items: items, total: total, page: page, size: size);
  }
}
