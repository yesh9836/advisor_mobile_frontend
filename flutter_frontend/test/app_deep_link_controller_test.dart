import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_frontend/services/app_deep_link_controller.dart';

void main() {
  test('routes Spectaculeads inbox links to the advisor inbox tab', () {
    final controller = AppDeepLinkController.instance;
    addTearDown(controller.clearRequest);

    controller.handleUri(Uri.parse('spectaculeads://inbox'));

    expect(controller.consumeAdvisorTab(0), 3);
    expect(controller.consumeAdvisorTab(0), 0);
  });

  test('ignores unrelated links', () {
    final controller = AppDeepLinkController.instance;
    addTearDown(controller.clearRequest);

    controller.handleUri(Uri.parse('https://app.rcntgroup.com/leads'));

    expect(controller.consumeAdvisorTab(2), 2);
  });
}
