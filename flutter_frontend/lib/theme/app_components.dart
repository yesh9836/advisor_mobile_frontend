import 'package:flutter/material.dart';
import 'package:flutter_frontend/theme/app_theme.dart';

class AppLoadingIndicator extends StatefulWidget {
  const AppLoadingIndicator({super.key, this.label, this.compact = false});

  final String? label;
  final bool compact;

  @override
  State<AppLoadingIndicator> createState() => _AppLoadingIndicatorState();
}

class _AppLoadingIndicatorState extends State<AppLoadingIndicator>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  )..repeat();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final size = widget.compact ? 6.0 : 8.0;
    return Semantics(
      label: widget.label ?? 'Loading',
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          AnimatedBuilder(
            animation: _controller,
            builder: (context, _) => Row(
              mainAxisSize: MainAxisSize.min,
              children: List.generate(3, (index) {
                final phase = (_controller.value - (index * .16)) % 1;
                final pulse = 1 - ((phase - .5).abs() * 2);
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 2.5),
                  child: Transform.translate(
                    offset: Offset(0, -4 * pulse),
                    child: Container(
                      width: size,
                      height: size,
                      decoration: BoxDecoration(
                        color: Color.lerp(
                          AppColors.cyan,
                          const Color(0xFF7964D9),
                          index / 2,
                        )!.withValues(alpha: .55 + (.45 * pulse)),
                        shape: BoxShape.circle,
                      ),
                    ),
                  ),
                );
              }),
            ),
          ),
          if (widget.label != null && !widget.compact) ...[
            const SizedBox(height: 9),
            Text(
              widget.label!,
              style: TextStyle(
                color: context.appMuted,
                fontSize: 11,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class AppRefreshIndicator extends StatefulWidget {
  const AppRefreshIndicator({
    super.key,
    required this.onRefresh,
    required this.child,
  });

  final RefreshCallback onRefresh;
  final Widget child;

  @override
  State<AppRefreshIndicator> createState() => _AppRefreshIndicatorState();
}

class _AppRefreshIndicatorState extends State<AppRefreshIndicator> {
  RefreshIndicatorStatus? _status;

  @override
  Widget build(BuildContext context) {
    final visible =
        _status == RefreshIndicatorStatus.armed ||
        _status == RefreshIndicatorStatus.snap ||
        _status == RefreshIndicatorStatus.refresh;
    return Stack(
      children: [
        RefreshIndicator.noSpinner(
          onRefresh: widget.onRefresh,
          onStatusChange: (status) {
            if (mounted) setState(() => _status = status);
          },
          child: widget.child,
        ),
        if (visible)
          Positioned(
            top: 8,
            left: 0,
            right: 0,
            child: IgnorePointer(
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 13,
                    vertical: 8,
                  ),
                  decoration: BoxDecoration(
                    color: context.appSurface.withValues(alpha: .96),
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(color: context.appOutline),
                    boxShadow: context.appCardShadows,
                  ),
                  child: const AppLoadingIndicator(
                    label: 'Refreshing',
                    compact: true,
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class AppScreenHeader extends StatelessWidget {
  const AppScreenHeader({
    super.key,
    required this.title,
    required this.subtitle,
    required this.icon,
    this.eyebrow,
    this.trailing,
    this.titleBadge,
  });

  final String title;
  final String subtitle;
  final String? eyebrow;
  final IconData icon;
  final Widget? trailing;
  final Widget? titleBadge;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            color: context.appInk,
                            fontSize: 23,
                            fontWeight: FontWeight.w900,
                            letterSpacing: -0.45,
                          ),
                        ),
                      ),
                      if (titleBadge != null) ...[
                        const SizedBox(width: 8),
                        titleBadge!,
                      ],
                    ],
                  ),
                  const SizedBox(height: 1),
                  Text(
                    subtitle,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: context.appMuted,
                      fontSize: 12.5,
                      height: 1.25,
                    ),
                  ),
                ],
              ),
            ),
            if (trailing != null) ...[const SizedBox(width: 10), trailing!],
          ],
        ),
      ],
    );
  }
}
