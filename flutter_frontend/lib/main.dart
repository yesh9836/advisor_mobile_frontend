import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_frontend/models/auth_models.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/screens/advisor/advisor_entry_screen.dart';
import 'package:flutter_frontend/screens/auth/login_screen.dart';
import 'package:flutter_frontend/services/api_service.dart';
import 'package:flutter_frontend/theme/app_theme.dart';
import 'package:flutter_frontend/theme/app_theme_controller.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const SpectaculeadsApp());
}

class SpectaculeadsApp extends StatefulWidget {
  const SpectaculeadsApp({super.key, this.authRepository});

  final AuthRepository? authRepository;

  @override
  State<SpectaculeadsApp> createState() => _SpectaculeadsAppState();
}

class _SpectaculeadsAppState extends State<SpectaculeadsApp> {
  final _themeController = AppThemeController();

  @override
  void dispose() {
    _themeController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AppThemeScope(
      controller: _themeController,
      child: AnimatedBuilder(
        animation: _themeController,
        builder: (context, _) => MaterialApp(
          title: 'Spectaculeads',
          debugShowCheckedModeBanner: false,
          theme: AppTheme.light,
          darkTheme: AppTheme.dark,
          themeMode: _themeController.mode,
          home: SessionBootstrap(authRepository: widget.authRepository),
        ),
      ),
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
  StreamSubscription<void>? _sessionExpiredSubscription;

  @override
  void initState() {
    super.initState();
    _sessionExpiredSubscription = ApiService.sessionExpiredEvents.listen((_) {
      if (!mounted) return;
      setState(() {
        _showLogin = true;
        _session = Future<UserProfile?>.value(null);
      });
    });
  }

  @override
  void dispose() {
    _sessionExpiredSubscription?.cancel();
    super.dispose();
  }

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
        if (snapshot.data != null) return const AdvisorEntryScreen();
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
      appBar: AppBar(
        actions: const [AppThemeToggleButton(), SizedBox(width: 16)],
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.cloud_off_outlined, color: context.appMuted, size: 42),
              const SizedBox(height: 16),
              Text(
                'Unable to restore your session',
                style: TextStyle(
                  color: context.appInk,
                  fontSize: 20,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Check your connection and try again.',
                textAlign: TextAlign.center,
                style: TextStyle(color: context.appMuted),
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
