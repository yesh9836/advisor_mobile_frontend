import 'package:flutter/material.dart';
import 'package:flutter_frontend/models/onboarding_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/screens/advisor/advisor_shell.dart';
import 'package:flutter_frontend/screens/advisor/onboarding_screen.dart';
import 'package:flutter_frontend/screens/auth/login_screen.dart';
import 'package:flutter_frontend/theme/app_theme.dart';

class AdvisorEntryScreen extends StatefulWidget {
  const AdvisorEntryScreen({
    super.key,
    this.advisorRepository,
    this.authRepository,
  });

  final AdvisorRepository? advisorRepository;
  final AuthRepository? authRepository;

  @override
  State<AdvisorEntryScreen> createState() => _AdvisorEntryScreenState();
}

class _AdvisorEntryScreenState extends State<AdvisorEntryScreen> {
  late final AdvisorRepository _advisorRepository =
      widget.advisorRepository ?? AdvisorRepository();
  late final AuthRepository _authRepository =
      widget.authRepository ?? AuthRepository();
  late Future<AdvisorOnboarding> _future = _advisorRepository.getOnboarding();

  void _retry() {
    setState(() => _future = _advisorRepository.getOnboarding());
  }

  void _finish(AdvisorOnboarding _) {
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const AdvisorShell(initialIndex: 2)),
      (_) => false,
    );
  }

  Future<void> _signOut() async {
    await _authRepository.logout();
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<AdvisorOnboarding>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        if (snapshot.hasError) {
          return Scaffold(
            body: Center(
              child: Padding(
                padding: const EdgeInsets.all(28),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.cloud_off_outlined,
                      color: context.appMuted,
                      size: 44,
                    ),
                    const SizedBox(height: 14),
                    Text(
                      'We couldn’t load your onboarding status.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: context.appInk,
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      snapshot.error.toString(),
                      textAlign: TextAlign.center,
                      style: TextStyle(color: context.appMuted),
                    ),
                    const SizedBox(height: 18),
                    FilledButton.icon(
                      onPressed: _retry,
                      icon: const Icon(Icons.refresh),
                      label: const Text('Try again'),
                    ),
                    TextButton(
                      onPressed: _signOut,
                      child: const Text('Sign out'),
                    ),
                  ],
                ),
              ),
            ),
          );
        }

        final onboarding = snapshot.data!;
        if (onboarding.complete) return const AdvisorShell();
        return AdvisorOnboardingScreen(
          mandatory: true,
          initialData: onboarding,
          advisorRepository: _advisorRepository,
          authRepository: _authRepository,
          onCompleted: _finish,
        );
      },
    );
  }
}
