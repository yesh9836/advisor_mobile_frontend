import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/foundation.dart';

class AppDeepLinkController {
  AppDeepLinkController._();

  static final AppDeepLinkController instance = AppDeepLinkController._();

  final ValueNotifier<int?> requestedAdvisorTab = ValueNotifier<int?>(null);
  final AppLinks _appLinks = AppLinks();
  StreamSubscription<Uri>? _subscription;

  void start() {
    _subscription ??= _appLinks.uriLinkStream.listen(
      _handleUri,
      onError: (_) {
        // A malformed external link must never interrupt session restoration.
      },
    );
  }

  void stop() {
    _subscription?.cancel();
    _subscription = null;
  }

  int consumeAdvisorTab(int fallback) {
    final requested = requestedAdvisorTab.value;
    requestedAdvisorTab.value = null;
    return requested?.clamp(0, 4).toInt() ?? fallback;
  }

  void clearRequest() {
    requestedAdvisorTab.value = null;
  }

  @visibleForTesting
  void handleUri(Uri uri) => _handleUri(uri);

  void _handleUri(Uri uri) {
    final isAppScheme = uri.scheme.toLowerCase() == 'spectaculeads';
    final destination = uri.host.toLowerCase();
    if (isAppScheme && const {'inbox', 'leads'}.contains(destination)) {
      requestedAdvisorTab.value = 3;
    }
  }
}
