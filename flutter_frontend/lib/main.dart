import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_frontend/models/auth_models.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/screens/advisor/advisor_entry_screen.dart';
import 'package:flutter_frontend/screens/auth/login_screen.dart';
import 'package:flutter_frontend/services/api_service.dart';
import 'package:flutter_frontend/services/app_deep_link_controller.dart';
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
  void initState() {
    super.initState();
    AppDeepLinkController.instance.start();
  }

  @override
  void dispose() {
    AppDeepLinkController.instance.stop();
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
          themeAnimationDuration: const Duration(milliseconds: 280),
          themeAnimationCurve: Curves.easeOutCubic,
          builder: (context, child) => _ThemeFlowTransition(
            isDark: _themeController.isDark,
            origin: _themeController.transitionOrigin,
            child: child ?? const SizedBox.shrink(),
          ),
          home: SessionBootstrap(authRepository: widget.authRepository),
        ),
      ),
    );
  }
}

class _ThemeFlowTransition extends StatefulWidget {
  const _ThemeFlowTransition({
    required this.isDark,
    required this.origin,
    required this.child,
  });

  final bool isDark;
  final Offset? origin;
  final Widget child;

  @override
  State<_ThemeFlowTransition> createState() => _ThemeFlowTransitionState();
}

class _ThemeFlowTransitionState extends State<_ThemeFlowTransition>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 320),
  );

  @override
  void didUpdateWidget(covariant _ThemeFlowTransition oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.isDark != widget.isDark) {
      _controller.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final size = Size(constraints.maxWidth, constraints.maxHeight);
        final origin = widget.origin ?? Offset(size.width - 34, 72);
        return Stack(
          fit: StackFit.expand,
          children: [
            RepaintBoundary(child: widget.child),
            Positioned.fill(
              child: IgnorePointer(
                child: RepaintBoundary(
                  child: CustomPaint(
                    key: const ValueKey('theme-flow-overlay'),
                    painter: _ThemeFlowPainter(
                      animation: _controller,
                      origin: origin,
                      maxRadius: _furthestCornerDistance(origin, size),
                      color: widget.isDark
                          ? const Color(0xFF050505)
                          : AppColors.canvas,
                      inverse: widget.isDark,
                    ),
                    isComplex: false,
                    willChange: true,
                  ),
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

double _furthestCornerDistance(Offset origin, Size size) {
  return [
    Offset.zero,
    Offset(size.width, 0),
    Offset(0, size.height),
    Offset(size.width, size.height),
  ].map((corner) => (corner - origin).distance).reduce((a, b) => a > b ? a : b);
}

class _ThemeFlowPainter extends CustomPainter {
  _ThemeFlowPainter({
    required this.animation,
    required this.origin,
    required this.maxRadius,
    required this.color,
    required this.inverse,
  }) : super(repaint: animation);

  final Animation<double> animation;
  final Offset origin;
  final double maxRadius;
  final Color color;
  final bool inverse;

  @override
  void paint(Canvas canvas, Size size) {
    if (!animation.isAnimating) return;
    final progress = Curves.easeOutCubic.transform(animation.value);
    final radius = inverse ? maxRadius * (1 - progress) : maxRadius * progress;
    final opacity = .28 * math.sin(math.pi * progress);
    if (radius <= 0 || opacity <= 0) return;
    final paint = Paint()..color = color.withValues(alpha: opacity);
    if (!inverse) {
      canvas.drawCircle(origin, radius, paint);
      return;
    }
    final path = Path()
      ..fillType = PathFillType.evenOdd
      ..addRect(Offset.zero & size)
      ..addOval(Rect.fromCircle(center: origin, radius: radius));
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant _ThemeFlowPainter oldDelegate) =>
      oldDelegate.animation != animation ||
      oldDelegate.maxRadius != maxRadius ||
      oldDelegate.color != color ||
      oldDelegate.origin != origin ||
      oldDelegate.inverse != inverse;
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
                fontWeight: FontWeight.w700,
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
      appBar: AppBar(),
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
                  fontWeight: FontWeight.w700,
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
