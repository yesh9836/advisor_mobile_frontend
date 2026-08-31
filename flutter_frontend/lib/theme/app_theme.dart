import 'package:flutter/material.dart';

abstract final class AppColors {
  static const midnight = Color(0xFF191C3B);
  static const indigo = Color(0xFF252D6D);
  static const cyan = Color(0xFF27B7CE);
  static const cyanBright = Color(0xFF5FD3E3);
  static const canvas = Color(0xFFF1F5F9);
  static const ink = Color(0xFF20234E);
  static const muted = Color(0xFF657786);
  static const outline = Color(0xFFDDE6ED);
}

abstract final class AppTheme {
  static ThemeData get light {
    final scheme = ColorScheme.fromSeed(
      seedColor: AppColors.midnight,
      brightness: Brightness.light,
      primary: AppColors.midnight,
      secondary: AppColors.cyan,
      surface: Colors.white,
      error: const Color(0xFFD92D4C),
    );

    final baseText = ThemeData.light().textTheme.apply(
      bodyColor: AppColors.ink,
      displayColor: AppColors.ink,
      fontFamily: 'sans-serif',
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: AppColors.canvas,
      textTheme: baseText.copyWith(
        headlineLarge: baseText.headlineLarge?.copyWith(
          fontWeight: FontWeight.w800,
          letterSpacing: -0.8,
        ),
        headlineMedium: baseText.headlineMedium?.copyWith(
          fontWeight: FontWeight.w800,
          letterSpacing: -0.5,
        ),
        titleLarge: baseText.titleLarge?.copyWith(
          fontWeight: FontWeight.w800,
          letterSpacing: -0.25,
        ),
        titleMedium: baseText.titleMedium?.copyWith(
          fontWeight: FontWeight.w700,
        ),
        bodyMedium: baseText.bodyMedium?.copyWith(
          color: AppColors.muted,
          height: 1.4,
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        foregroundColor: AppColors.midnight,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: AppColors.midnight,
          fontSize: 20,
          fontWeight: FontWeight.w800,
          letterSpacing: -0.3,
        ),
      ),
      cardTheme: CardThemeData(
        color: Colors.white,
        surfaceTintColor: Colors.white,
        elevation: 3,
        shadowColor: const Color(0x33173A54),
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppColors.outline),
        ),
      ),
      dividerTheme: const DividerThemeData(
        color: Color(0xFFE7EDF2),
        thickness: 1,
        space: 1,
      ),
      chipTheme: ChipThemeData(
        backgroundColor: const Color(0xFFEAF9FC),
        selectedColor: AppColors.midnight,
        checkmarkColor: Colors.white,
        labelStyle: const TextStyle(
          color: AppColors.ink,
          fontSize: 12,
          fontWeight: FontWeight.w700,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 3),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(999),
          side: const BorderSide(color: AppColors.outline),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        height: 64,
        elevation: 0,
        backgroundColor: Colors.white,
        indicatorColor: Colors.transparent,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        labelTextStyle: WidgetStateProperty.resolveWith(
          (states) => TextStyle(
            color: states.contains(WidgetState.selected)
                ? const Color(0xFF078AA2)
                : const Color(0xFF556273),
            fontSize: 10,
            fontWeight: states.contains(WidgetState.selected)
                ? FontWeight.w800
                : FontWeight.w600,
          ),
        ),
        iconTheme: WidgetStateProperty.resolveWith(
          (states) => IconThemeData(
            color: states.contains(WidgetState.selected)
                ? const Color(0xFF078AA2)
                : const Color(0xFF556273),
            size: 21,
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        hintStyle: const TextStyle(color: Color(0xFF95A4AF)),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 13,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(15),
          borderSide: const BorderSide(color: AppColors.outline),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(15),
          borderSide: const BorderSide(color: AppColors.outline),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(15),
          borderSide: const BorderSide(color: AppColors.cyan, width: 1.5),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.cyan,
          foregroundColor: Colors.white,
          disabledBackgroundColor: const Color(0xFFB9DDE3),
          minimumSize: const Size.fromHeight(46),
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(15),
          ),
          textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.midnight,
          side: const BorderSide(color: AppColors.outline),
          minimumSize: const Size(48, 48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(15),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AppColors.cyan,
          textStyle: const TextStyle(fontWeight: FontWeight.w800),
        ),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.white,
        showDragHandle: true,
        dragHandleColor: Color(0xFFCAD6DE),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppColors.midnight,
        contentTextStyle: const TextStyle(color: Colors.white),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: AppColors.cyan,
      ),
    );
  }

  static ThemeData get dark {
    const canvas = Color(0xFF08111F);
    const surface = Color(0xFF111C2E);
    const surfaceRaised = Color(0xFF17243A);
    const ink = Color(0xFFEAF0F8);
    const muted = Color(0xFF9DACC0);
    const outline = Color(0xFF2A3A52);
    const cyan = Color(0xFF4BC9DA);

    const scheme = ColorScheme.dark(
      primary: cyan,
      onPrimary: Color(0xFF04161C),
      secondary: Color(0xFF7DDDE8),
      onSecondary: Color(0xFF04161C),
      surface: surface,
      onSurface: ink,
      onSurfaceVariant: muted,
      outline: Color(0xFF405169),
      outlineVariant: outline,
      error: Color(0xFFFF6B7D),
      onError: Color(0xFF2A050B),
    );

    final baseText = ThemeData.dark().textTheme.apply(
      bodyColor: ink,
      displayColor: ink,
      fontFamily: 'sans-serif',
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: canvas,
      canvasColor: canvas,
      shadowColor: Colors.black,
      textTheme: baseText.copyWith(
        headlineLarge: baseText.headlineLarge?.copyWith(
          fontWeight: FontWeight.w800,
          letterSpacing: -0.8,
        ),
        headlineMedium: baseText.headlineMedium?.copyWith(
          fontWeight: FontWeight.w800,
          letterSpacing: -0.5,
        ),
        titleLarge: baseText.titleLarge?.copyWith(
          fontWeight: FontWeight.w800,
          letterSpacing: -0.25,
        ),
        titleMedium: baseText.titleMedium?.copyWith(
          fontWeight: FontWeight.w700,
        ),
        bodyMedium: baseText.bodyMedium?.copyWith(color: muted, height: 1.4),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        foregroundColor: ink,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: ink,
          fontSize: 20,
          fontWeight: FontWeight.w800,
          letterSpacing: -0.3,
        ),
      ),
      cardTheme: CardThemeData(
        color: surface,
        surfaceTintColor: surface,
        elevation: 3,
        shadowColor: Colors.black.withValues(alpha: 0.72),
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: outline),
        ),
      ),
      dividerTheme: const DividerThemeData(
        color: outline,
        thickness: 1,
        space: 1,
      ),
      chipTheme: ChipThemeData(
        backgroundColor: surfaceRaised,
        selectedColor: cyan,
        checkmarkColor: const Color(0xFF04161C),
        labelStyle: const TextStyle(
          color: ink,
          fontSize: 12,
          fontWeight: FontWeight.w700,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 3),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(999),
          side: const BorderSide(color: outline),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        height: 64,
        elevation: 0,
        backgroundColor: surface,
        indicatorColor: Colors.transparent,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        labelTextStyle: WidgetStateProperty.resolveWith(
          (states) => TextStyle(
            color: states.contains(WidgetState.selected)
                ? cyan
                : const Color(0xFF8290A5),
            fontSize: 10,
            fontWeight: states.contains(WidgetState.selected)
                ? FontWeight.w800
                : FontWeight.w600,
          ),
        ),
        iconTheme: WidgetStateProperty.resolveWith(
          (states) => IconThemeData(
            color: states.contains(WidgetState.selected)
                ? cyan
                : const Color(0xFF8290A5),
            size: 21,
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surfaceRaised,
        labelStyle: const TextStyle(color: muted),
        hintStyle: const TextStyle(color: Color(0xFF718198)),
        prefixIconColor: muted,
        suffixIconColor: muted,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 13,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(15),
          borderSide: const BorderSide(color: outline),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(15),
          borderSide: const BorderSide(color: outline),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(15),
          borderSide: const BorderSide(color: cyan, width: 1.5),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: cyan,
          foregroundColor: const Color(0xFF04161C),
          disabledBackgroundColor: const Color(0xFF274550),
          minimumSize: const Size.fromHeight(46),
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(15),
          ),
          textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: ink,
          side: const BorderSide(color: outline),
          minimumSize: const Size(48, 48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(15),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: cyan,
          textStyle: const TextStyle(fontWeight: FontWeight.w800),
        ),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: surface,
        surfaceTintColor: surface,
        showDragHandle: true,
        dragHandleColor: Color(0xFF41516A),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
        ),
      ),
      dialogTheme: const DialogThemeData(
        backgroundColor: surface,
        surfaceTintColor: surface,
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: const Color(0xFF1E304A),
        contentTextStyle: const TextStyle(color: ink),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(color: cyan),
    );
  }
}

extension AppThemeContext on BuildContext {
  ColorScheme get appScheme => Theme.of(this).colorScheme;
  bool get isDarkMode => Theme.of(this).brightness == Brightness.dark;
  Color get appCanvas => Theme.of(this).scaffoldBackgroundColor;
  Color get appSurface => appScheme.surface;
  Color get appSurfaceRaised =>
      isDarkMode ? const Color(0xFF17243A) : Colors.white;
  Color get appInk => appScheme.onSurface;
  Color get appMuted => appScheme.onSurfaceVariant;
  Color get appOutline => appScheme.outlineVariant;
  Color get appSoftFill =>
      isDarkMode ? const Color(0xFF152338) : const Color(0xFFF4FAFC);
  List<BoxShadow> get appCardShadows => isDarkMode
      ? [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.34),
            blurRadius: 20,
            offset: const Offset(0, 9),
          ),
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.16),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ]
      : const [
          BoxShadow(
            color: Color(0x1F173A54),
            blurRadius: 20,
            offset: Offset(0, 8),
          ),
          BoxShadow(
            color: Color(0x0D173A54),
            blurRadius: 4,
            offset: Offset(0, 2),
          ),
        ];
}
