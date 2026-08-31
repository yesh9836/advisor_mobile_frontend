import 'package:flutter/material.dart';

class AppThemeController extends ChangeNotifier {
  ThemeMode _mode = ThemeMode.light;

  ThemeMode get mode => _mode;
  bool get isDark => _mode == ThemeMode.dark;

  void toggle() {
    _mode = isDark ? ThemeMode.light : ThemeMode.dark;
    notifyListeners();
  }
}

class AppThemeScope extends InheritedNotifier<AppThemeController> {
  const AppThemeScope({
    super.key,
    required AppThemeController controller,
    required super.child,
  }) : super(notifier: controller);

  static AppThemeController of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppThemeScope>();
    assert(scope != null, 'AppThemeScope is missing above this context.');
    return scope!.notifier!;
  }

  static AppThemeController? maybeOf(BuildContext context) {
    return context
        .dependOnInheritedWidgetOfExactType<AppThemeScope>()
        ?.notifier;
  }
}

class AppThemeToggleButton extends StatelessWidget {
  const AppThemeToggleButton({super.key});

  @override
  Widget build(BuildContext context) {
    final controller = AppThemeScope.maybeOf(context);
    if (controller == null) return const SizedBox.shrink();
    final colors = Theme.of(context).colorScheme;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Tooltip(
      message: isDark ? 'Use light theme' : 'Use dark theme',
      child: Material(
        color: colors.surface,
        shape: const CircleBorder(),
        child: InkWell(
          onTap: controller.toggle,
          customBorder: const CircleBorder(),
          child: Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: colors.outlineVariant),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: isDark ? 0.22 : 0.06),
                  blurRadius: 10,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 180),
              transitionBuilder: (child, animation) =>
                  RotationTransition(turns: animation, child: child),
              child: Icon(
                isDark ? Icons.light_mode_rounded : Icons.dark_mode_rounded,
                key: ValueKey(isDark),
                color: isDark ? const Color(0xFFFFC857) : colors.primary,
                size: 19,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
