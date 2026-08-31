import 'package:flutter/material.dart';
import 'package:flutter_frontend/theme/app_theme.dart';
import 'package:flutter_frontend/theme/app_theme_controller.dart';

class AppScreenHeader extends StatelessWidget {
  const AppScreenHeader({
    super.key,
    required this.title,
    required this.subtitle,
    required this.icon,
    this.eyebrow,
    this.trailing,
  });

  final String title;
  final String subtitle;
  final String? eyebrow;
  final IconData icon;
  final Widget? trailing;

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
                  Text(
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
            const SizedBox(width: 8),
            const AppThemeToggleButton(),
          ],
        ),
      ],
    );
  }
}
