import 'package:flutter_frontend/theme/app_theme.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('uses the professional Plus Jakarta Sans type system in both themes', () {
    for (final theme in [AppTheme.light, AppTheme.dark]) {
      expect(theme.textTheme.bodyMedium?.fontFamily, 'PlusJakartaSans');
      expect(theme.textTheme.headlineMedium?.fontWeight?.value, 600);
      expect(theme.textTheme.bodyMedium?.fontWeight?.value, 400);
      expect(theme.textTheme.bodyMedium?.fontFeatures, isNotEmpty);
    }
  });
}
