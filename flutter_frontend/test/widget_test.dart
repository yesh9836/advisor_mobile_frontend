import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_frontend/main.dart';

void main() {
  testWidgets('shows advisor login screen', (WidgetTester tester) async {
    await tester.pumpWidget(const SpectaculeadsApp());

    expect(find.text('Spectaculeads'), findsOneWidget);
    expect(find.text('Sign In'), findsOneWidget);
  });
}
