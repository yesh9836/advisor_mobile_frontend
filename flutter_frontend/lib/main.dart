import 'package:flutter/material.dart';
import 'package:flutter_frontend/screens/auth/login_screen.dart';

void main() {
  runApp(const SpectaculeadsApp());
}

class SpectaculeadsApp extends StatelessWidget {
  const SpectaculeadsApp({super.key});

  @override
  Widget build(BuildContext context) {
    const navy = Color(0xFF202860);
    const teal = Color(0xFF18A0B8);

    return MaterialApp(
      title: 'Spectaculeads',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: navy,
          primary: navy,
          secondary: teal,
          surface: Colors.white,
        ),
        scaffoldBackgroundColor: const Color(0xFFF2F8FB),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFFF2F8FB),
          foregroundColor: navy,
          elevation: 0,
          centerTitle: false,
        ),
        cardTheme: CardThemeData(
          color: Colors.white,
          elevation: 0,
          margin: EdgeInsets.zero,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
            side: const BorderSide(color: Color(0xFFCFE4EC)),
          ),
        ),
        chipTheme: ChipThemeData(
          backgroundColor: const Color(0xFFEAF8FC),
          selectedColor: const Color(0xFFE3E1FF),
          labelStyle: const TextStyle(
            color: navy,
            fontSize: 12,
            fontWeight: FontWeight.w800,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
            side: const BorderSide(color: Color(0xFFCFE4EC)),
          ),
        ),
        navigationBarTheme: NavigationBarThemeData(
          backgroundColor: Colors.white,
          indicatorColor: const Color(0xFFE6E3FB),
          labelTextStyle: WidgetStateProperty.resolveWith(
            (states) => TextStyle(
              color: states.contains(WidgetState.selected)
                  ? navy
                  : const Color(0xFF607987),
              fontSize: 11,
              fontWeight: FontWeight.w800,
            ),
          ),
          iconTheme: WidgetStateProperty.resolveWith(
            (states) => IconThemeData(
              color: states.contains(WidgetState.selected)
                  ? navy
                  : const Color(0xFF607987),
              size: 22,
            ),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: const Color(0xFFF7FBFD),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: teal),
          ),
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            backgroundColor: navy,
            foregroundColor: Colors.white,
            minimumSize: const Size.fromHeight(46),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
            ),
            textStyle: const TextStyle(fontWeight: FontWeight.w900),
          ),
        ),
        useMaterial3: true,
      ),
      home: const LoginScreen(),
    );
  }
}
