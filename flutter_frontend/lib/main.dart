import 'package:flutter/material.dart';
import 'package:flutter_frontend/models/auth_models.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/screens/advisor/advisor_shell.dart';
import 'package:flutter_frontend/screens/auth/login_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const SpectaculeadsApp());
}

class SpectaculeadsApp extends StatelessWidget {
  const SpectaculeadsApp({super.key, this.authRepository});

  final AuthRepository? authRepository;

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
      home: SessionBootstrap(authRepository: authRepository),
    );
  }
}

class SessionBootstrap extends StatefulWidget {
  const SessionBootstrap({super.key, this.authRepository});

  final AuthRepository? authRepository;

  @override
  State<SessionBootstrap> createState() => _SessionBootstrapState();
}

class _SessionBootstrapState extends State<SessionBootstrap> {
  late final AuthRepository _authRepository =
      widget.authRepository ?? AuthRepository();
  late Future<UserProfile?> _session = _authRepository.restoreSession();
  bool _showLogin = false;

  void _retry() {
    setState(() {
      _showLogin = false;
      _session = _authRepository.restoreSession();
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_showLogin) return const LoginScreen();

    return FutureBuilder<UserProfile?>(
      future: _session,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const _SessionLoadingScreen();
        }
        if (snapshot.hasError) {
          return _SessionRestoreError(
            onRetry: _retry,
            onSignIn: () => setState(() => _showLogin = true),
          );
        }
        if (snapshot.data != null) return const AdvisorShell();
        return const LoginScreen();
      },
    );
  }
}

class _SessionLoadingScreen extends StatelessWidget {
  const _SessionLoadingScreen();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: Color(0xFF252D6D),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.bar_chart_rounded, color: Colors.white, size: 44),
            SizedBox(height: 20),
            Text(
              'Spectaculeads',
              style: TextStyle(
                color: Colors.white,
                fontSize: 24,
                fontWeight: FontWeight.w900,
              ),
            ),
            SizedBox(height: 20),
            CircularProgressIndicator(color: Colors.white),
          ],
        ),
      ),
    );
  }
}

class _SessionRestoreError extends StatelessWidget {
  const _SessionRestoreError({required this.onRetry, required this.onSignIn});

  final VoidCallback onRetry;
  final VoidCallback onSignIn;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.cloud_off_outlined,
                color: Color(0xFF58707D),
                size: 42,
              ),
              const SizedBox(height: 16),
              const Text(
                'Unable to restore your session',
                style: TextStyle(
                  color: Color(0xFF202860),
                  fontSize: 20,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Check your connection and try again.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Color(0xFF58707D)),
              ),
              const SizedBox(height: 20),
              FilledButton(onPressed: onRetry, child: const Text('Retry')),
              TextButton(onPressed: onSignIn, child: const Text('Sign in')),
            ],
          ),
        ),
      ),
    );
  }
}
