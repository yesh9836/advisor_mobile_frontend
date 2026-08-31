import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/theme/app_components.dart';
import 'package:flutter_frontend/theme/app_theme.dart';

class GoalsScreen extends StatefulWidget {
  const GoalsScreen({
    super.key,
    required this.onSeeAllPackages,
    this.repository,
  });

  final VoidCallback onSeeAllPackages;
  final AdvisorRepository? repository;

  @override
  State<GoalsScreen> createState() => _GoalsScreenState();
}

class _GoalsScreenState extends State<GoalsScreen> {
  late final AdvisorRepository _repository =
      widget.repository ?? AdvisorRepository();
  late Future<GoalSnapshot> _future = _repository.getGoal();
  GoalSnapshot? _savedGoal;

  void _retry() {
    setState(() {
      _savedGoal = null;
      _future = _repository.getGoal();
    });
  }

  Future<void> _saveMonthlyGoal(
    GoalSnapshot currentGoal,
    int monthlyGoalCents,
  ) async {
    final updated = await _repository.saveMonthlyGoal(
      currentGoal: currentGoal,
      monthlyGoalCents: monthlyGoalCents,
    );
    if (!mounted) return;
    setState(() {
      _savedGoal = updated;
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<GoalSnapshot>(
      future: _future,
      builder: (context, snapshot) {
        final goal = _savedGoal ?? snapshot.data;
        return ListView(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 18),
          children: [
            const AppScreenHeader(
              eyebrow: 'Performance plan',
              title: 'Goals',
              subtitle: 'Track your annual target and next best actions.',
              icon: Icons.track_changes_rounded,
            ),
            const SizedBox(height: 12),
            if (snapshot.connectionState == ConnectionState.waiting)
              const Center(child: CircularProgressIndicator())
            else if (snapshot.hasError)
              _Panel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(snapshot.error.toString()),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed: _retry,
                      icon: const Icon(Icons.refresh),
                      label: const Text('Retry'),
                    ),
                  ],
                ),
              )
            else ...[
              _GoalHero(goal: goal!),
              const SizedBox(height: 10),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                mainAxisExtent: 100,
                children: [
                  _StatCard(
                    value: '${goal.dealsRemaining}',
                    label: 'Deals Remaining',
                    icon: Icons.emoji_events_outlined,
                  ),
                  _StatCard(
                    value: '${goal.appointmentsRemaining}',
                    label: 'Appointments Remaining',
                    icon: Icons.calendar_today_outlined,
                  ),
                  _StatCard(
                    value: '${goal.leadsRemaining}',
                    label: 'Leads Remaining',
                    icon: Icons.group_outlined,
                  ),
                  _StatCard(
                    value: '${goal.closedDealsYtd}',
                    label: 'Closed YTD',
                    icon: Icons.check_circle_outline_rounded,
                  ),
                ],
              ),
              const SizedBox(height: 10),
              _GoalTrendCard(goal: goal),
              const SizedBox(height: 10),
              _MonthlyGoalPanel(
                monthlyGoalCents: (goal.annualGoalCents / 12).round(),
                onSave: (monthlyGoalCents) =>
                    _saveMonthlyGoal(goal, monthlyGoalCents),
              ),
              if (goal.pacingMessage.isNotEmpty) ...[
                const SizedBox(height: 10),
                _PacingPanel(goal: goal),
              ],
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Recommended Packages',
                      style: TextStyle(
                        color: context.appInk,
                        fontSize: 16,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ),
                  TextButton(
                    onPressed: widget.onSeeAllPackages,
                    child: const Text('See all →'),
                  ),
                ],
              ),
              if (goal.packages.isEmpty)
                _Panel(
                  child: Text(
                    goal.pacingStatus == 'goal_met'
                        ? 'Annual income goal met. No additional lead packages are needed.'
                        : 'No current lead packages are available.',
                  ),
                )
              else
                SizedBox(
                  height: 196,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: goal.packages.length,
                    separatorBuilder: (_, _) => const SizedBox(width: 12),
                    itemBuilder: (context, index) => _PackagePreview(
                      package: goal.packages[index],
                      onSelect: widget.onSeeAllPackages,
                    ),
                  ),
                ),
            ],
          ],
        );
      },
    );
  }
}

class _GoalHero extends StatelessWidget {
  const _GoalHero({required this.goal});

  final GoalSnapshot goal;

  @override
  Widget build(BuildContext context) {
    final progress = goal.incomeProgressPercent.clamp(0, 100) / 100;

    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        boxShadow: const [
          BoxShadow(
            color: Color(0x33202860),
            blurRadius: 24,
            offset: Offset(0, 14),
          ),
        ],
      ),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          gradient: const LinearGradient(
            colors: [Color(0xFF29347E), Color(0xFF126D7A)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        child: Column(
          children: [
            Row(
              children: [
                SizedBox(
                  width: 88,
                  height: 88,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      SizedBox.expand(
                        child: CircularProgressIndicator(
                          value: progress,
                          strokeWidth: 8,
                          backgroundColor: Colors.white24,
                          color: const Color(0xFF19B9D0),
                          strokeCap: StrokeCap.round,
                        ),
                      ),
                      Text(
                        '${goal.incomeProgressPercent}%\nof goal',
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w900,
                          height: 1.1,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Earned',
                        style: TextStyle(color: Colors.white70),
                      ),
                      Text(
                        _money(goal.earnedYtdCents),
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 23,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'Target',
                        style: TextStyle(color: Colors.white70),
                      ),
                      Text(
                        _money(goal.annualGoalCents),
                        style: const TextStyle(
                          color: Color(0xFF7DD3FC),
                          fontSize: 18,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 13),
            ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                value: progress,
                minHeight: 6,
                backgroundColor: Colors.white24,
                color: const Color(0xFF19B9D0),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

enum _TrendRange { sevenDays, month, year }

extension on _TrendRange {
  String get label => switch (this) {
    _TrendRange.sevenDays => '7 Days',
    _TrendRange.month => 'Month',
    _TrendRange.year => 'Year',
  };
}

class _GoalTrendCard extends StatefulWidget {
  const _GoalTrendCard({required this.goal});

  final GoalSnapshot goal;

  @override
  State<_GoalTrendCard> createState() => _GoalTrendCardState();
}

class _GoalTrendCardState extends State<_GoalTrendCard> {
  _TrendRange _range = _TrendRange.year;

  @override
  Widget build(BuildContext context) {
    final goal = widget.goal;
    final trend = _GoalTrend.fromGoal(goal, DateTime.now());
    final requiredCents = switch (_range) {
      _TrendRange.sevenDays => (goal.annualGoalCents * 7 / 365).round(),
      _TrendRange.month => (goal.annualGoalCents / 12).round(),
      _TrendRange.year => trend.expectedCents,
    };
    final paceRatio = trend.expectedCents <= 0
        ? 0.0
        : goal.earnedYtdCents / trend.expectedCents;
    final demoActualCents = _range == _TrendRange.year
        ? goal.earnedYtdCents
        : (requiredCents * paceRatio).round();
    final targetCents = _range == _TrendRange.year
        ? goal.annualGoalCents
        : requiredCents;
    final chartElapsed = _range == _TrendRange.year
        ? trend.elapsedFraction
        : 1.0;
    final chartProjected = _range == _TrendRange.year
        ? trend.projectedCents
        : demoActualCents;

    return _Panel(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Income trend',
                      style: TextStyle(
                        color: context.appInk,
                        fontSize: 16,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Illustrative progress against the required goal pace',
                      style: TextStyle(color: context.appMuted, fontSize: 11.5),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              _TrendStatusBadge(trend: trend),
            ],
          ),
          const SizedBox(height: 12),
          _TrendRangeSelector(
            selected: _range,
            onSelected: (range) => setState(() => _range = range),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              const Icon(
                Icons.science_outlined,
                size: 14,
                color: Color(0xFF078AA2),
              ),
              const SizedBox(width: 5),
              Text(
                'Demo trend data for visualization',
                style: TextStyle(
                  color: context.appMuted,
                  fontSize: 10.5,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Semantics(
            label:
                '${_range.label} demo trend. ${trend.label}. '
                'Required ${_money(requiredCents)}. '
                'Visualized ${_money(demoActualCents)}.',
            child: SizedBox(
              height: 174,
              width: double.infinity,
              child: CustomPaint(
                painter: _GoalTrendPainter(
                  range: _range,
                  actualCents: demoActualCents,
                  targetCents: targetCents,
                  projectedCents: chartProjected,
                  elapsedFraction: chartElapsed,
                  actualColor: trend.color,
                  goalColor: context.isDarkMode
                      ? const Color(0xFF7DDDE8)
                      : const Color(0xFF078AA2),
                  gridColor: context.appOutline,
                  labelColor: context.appMuted,
                ),
              ),
            ),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _TrendMetric(
                  label: _range == _TrendRange.year
                      ? 'Expected by today'
                      : 'Required in ${_range.label.toLowerCase()}',
                  value: _money(requiredCents),
                ),
              ),
              Container(width: 1, height: 34, color: context.appOutline),
              const SizedBox(width: 14),
              Expanded(
                child: _TrendMetric(
                  label: _range == _TrendRange.year
                      ? 'Projected year end'
                      : 'Demo earnings',
                  value: _money(
                    _range == _TrendRange.year
                        ? trend.projectedCents
                        : demoActualCents,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            trend.summary,
            style: TextStyle(
              color: context.appMuted,
              fontSize: 12,
              height: 1.35,
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 14,
            runSpacing: 6,
            children: [
              const _TrendLegend(color: Color(0xFF078AA2), label: 'Goal pace'),
              _TrendLegend(
                color: trend.color,
                label: _range == _TrendRange.year
                    ? 'Demo actual / projection'
                    : 'Demo actual',
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _TrendRangeSelector extends StatelessWidget {
  const _TrendRangeSelector({required this.selected, required this.onSelected});

  final _TrendRange selected;
  final ValueChanged<_TrendRange> onSelected;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: context.appSoftFill,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: context.appOutline),
      ),
      child: Row(
        children: [
          for (final range in _TrendRange.values)
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 2),
                child: Material(
                  color: selected == range
                      ? context.appSurface
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(9),
                  child: InkWell(
                    key: ValueKey('trend-range-${range.name}'),
                    onTap: () => onSelected(range),
                    borderRadius: BorderRadius.circular(9),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 180),
                      alignment: Alignment.center,
                      padding: const EdgeInsets.symmetric(vertical: 9),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(9),
                        border: selected == range
                            ? Border.all(color: const Color(0xFF27B7CE))
                            : null,
                      ),
                      child: Text(
                        range.label,
                        style: TextStyle(
                          color: selected == range
                              ? const Color(0xFF078AA2)
                              : context.appMuted,
                          fontSize: 12,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _TrendStatusBadge extends StatelessWidget {
  const _TrendStatusBadge({required this.trend});

  final _GoalTrend trend;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: trend.color.withValues(alpha: context.isDarkMode ? 0.18 : 0.11),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: trend.color.withValues(alpha: 0.42)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(trend.icon, size: 14, color: trend.color),
          const SizedBox(width: 5),
          Text(
            trend.label,
            style: TextStyle(
              color: trend.color,
              fontSize: 11,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    );
  }
}

class _TrendMetric extends StatelessWidget {
  const _TrendMetric({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: TextStyle(color: context.appMuted, fontSize: 10.5)),
        const SizedBox(height: 2),
        Text(
          value,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
            color: context.appInk,
            fontSize: 15,
            fontWeight: FontWeight.w900,
          ),
        ),
      ],
    );
  }
}

class _TrendLegend extends StatelessWidget {
  const _TrendLegend({required this.color, required this.label});

  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 16,
          height: 3,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(99),
          ),
        ),
        const SizedBox(width: 6),
        Text(label, style: TextStyle(color: context.appMuted, fontSize: 10.5)),
      ],
    );
  }
}

class _GoalTrend {
  const _GoalTrend({
    required this.elapsedFraction,
    required this.expectedCents,
    required this.projectedCents,
    required this.label,
    required this.summary,
    required this.color,
    required this.icon,
  });

  final double elapsedFraction;
  final int expectedCents;
  final int projectedCents;
  final String label;
  final String summary;
  final Color color;
  final IconData icon;

  factory _GoalTrend.fromGoal(GoalSnapshot goal, DateTime now) {
    final yearStart = DateTime(goal.targetYear);
    final yearEnd = DateTime(goal.targetYear + 1);
    final elapsedFraction = now.isBefore(yearStart)
        ? 0.0
        : now.isAfter(yearEnd)
        ? 1.0
        : now.difference(yearStart).inMinutes /
              yearEnd.difference(yearStart).inMinutes;
    final boundedElapsed = elapsedFraction.clamp(0.0, 1.0);
    final expectedCents = (goal.annualGoalCents * boundedElapsed).round();
    final projectedCents = boundedElapsed <= 0
        ? goal.earnedYtdCents
        : (goal.earnedYtdCents / boundedElapsed).round();

    if (goal.annualGoalCents > 0 &&
        goal.earnedYtdCents >= goal.annualGoalCents) {
      return _GoalTrend(
        elapsedFraction: boundedElapsed,
        expectedCents: expectedCents,
        projectedCents: projectedCents,
        label: 'Goal achieved',
        summary:
            'The annual goal has already been reached. Keep the current momentum going.',
        color: const Color(0xFF059669),
        icon: Icons.verified_rounded,
      );
    }

    if (boundedElapsed <= 0 || expectedCents <= 0) {
      return _GoalTrend(
        elapsedFraction: boundedElapsed,
        expectedCents: expectedCents,
        projectedCents: projectedCents,
        label: 'Plan ready',
        summary: 'Tracking will begin when the target year starts.',
        color: const Color(0xFF078AA2),
        icon: Icons.event_available_rounded,
      );
    }

    final paceRatio = goal.earnedYtdCents / expectedCents;
    if (paceRatio > 1.05) {
      return _GoalTrend(
        elapsedFraction: boundedElapsed,
        expectedCents: expectedCents,
        projectedCents: projectedCents,
        label: 'Ahead of pace',
        summary:
            '${_money(goal.earnedYtdCents - expectedCents)} ahead of the required pace today.',
        color: const Color(0xFF059669),
        icon: Icons.trending_up_rounded,
      );
    }
    if (paceRatio >= 0.95) {
      return _GoalTrend(
        elapsedFraction: boundedElapsed,
        expectedCents: expectedCents,
        projectedCents: projectedCents,
        label: 'On track',
        summary: 'Current earnings are within 5% of the required goal pace.',
        color: const Color(0xFF078AA2),
        icon: Icons.track_changes_rounded,
      );
    }
    return _GoalTrend(
      elapsedFraction: boundedElapsed,
      expectedCents: expectedCents,
      projectedCents: projectedCents,
      label: 'Behind pace',
      summary:
          '${_money(expectedCents - goal.earnedYtdCents)} below the required pace today. Increase lead and appointment activity to close the gap.',
      color: const Color(0xFFE05252),
      icon: Icons.trending_down_rounded,
    );
  }
}

class _GoalTrendPainter extends CustomPainter {
  const _GoalTrendPainter({
    required this.range,
    required this.actualCents,
    required this.targetCents,
    required this.projectedCents,
    required this.elapsedFraction,
    required this.actualColor,
    required this.goalColor,
    required this.gridColor,
    required this.labelColor,
  });

  final _TrendRange range;
  final int actualCents;
  final int targetCents;
  final int projectedCents;
  final double elapsedFraction;
  final Color actualColor;
  final Color goalColor;
  final Color gridColor;
  final Color labelColor;

  @override
  void paint(Canvas canvas, Size size) {
    const left = 4.0;
    const top = 8.0;
    const bottom = 24.0;
    final chartHeight = size.height - top - bottom;
    final chartWidth = size.width - left - 4;
    final maxCents = <int>[
      targetCents,
      actualCents,
      projectedCents,
      1,
    ].reduce((a, b) => a > b ? a : b);
    final yMax = maxCents * 1.12;

    double x(double fraction) => left + chartWidth * fraction.clamp(0, 1);
    double y(num cents) => top + chartHeight * (1 - cents / yMax);

    final gridPaint = Paint()
      ..color = gridColor.withValues(alpha: 0.72)
      ..strokeWidth = 1;
    for (var index = 0; index <= 3; index++) {
      final gridY = top + chartHeight * index / 3;
      canvas.drawLine(
        Offset(left, gridY),
        Offset(size.width, gridY),
        gridPaint,
      );
    }

    final goalPaint = Paint()
      ..color = goalColor
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(
      Offset(x(0), y(0)),
      Offset(x(1), y(targetCents)),
      goalPaint,
    );

    final currentX = elapsedFraction.clamp(0.0, 1.0);
    final actualPaint = Paint()
      ..color = actualColor
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    final history = switch (range) {
      _TrendRange.sevenDays => const <double>[
        0.24,
        0.52,
        0.36,
        0.71,
        0.49,
        0.83,
        1.00,
      ],
      _TrendRange.month => const <double>[
        0.18,
        0.44,
        0.31,
        0.63,
        0.47,
        0.79,
        0.66,
        1.00,
      ],
      _TrendRange.year => const <double>[
        0.00,
        0.18,
        0.11,
        0.34,
        0.25,
        0.49,
        0.39,
        0.67,
        0.55,
        0.81,
        0.70,
        1.00,
      ],
    };
    final demoPoints = <Offset>[
      for (var index = 0; index < history.length; index++)
        Offset(
          x(currentX * index / (history.length - 1)),
          y(actualCents * history[index]),
        ),
    ];
    final demoPath = Path()..moveTo(demoPoints.first.dx, demoPoints.first.dy);
    for (final point in demoPoints.skip(1)) {
      demoPath.lineTo(point.dx, point.dy);
    }
    canvas.drawPath(demoPath, actualPaint);
    final pointPaint = Paint()..color = actualColor;
    for (final point in demoPoints) {
      canvas.drawCircle(point, 2.6, pointPaint);
    }
    canvas.drawCircle(demoPoints.last, 4.5, pointPaint);

    if (currentX < 1) {
      _drawDashedLine(
        canvas,
        Offset(x(currentX), y(actualCents)),
        Offset(x(1), y(projectedCents)),
        actualPaint..strokeWidth = 2,
      );
    }

    final labels = switch (range) {
      _TrendRange.sevenDays => const <(double, String)>[
        (0, '7d ago'),
        (0.33, '5d'),
        (0.66, '3d'),
        (1, 'Today'),
      ],
      _TrendRange.month => const <(double, String)>[
        (0, 'Week 1'),
        (0.33, 'Week 2'),
        (0.66, 'Week 3'),
        (1, 'Week 4'),
      ],
      _TrendRange.year => const <(double, String)>[
        (0, 'Jan'),
        (0.25, 'Apr'),
        (0.5, 'Jul'),
        (0.75, 'Oct'),
        (1, 'Dec'),
      ],
    };
    for (final label in labels) {
      final painter = TextPainter(
        text: TextSpan(
          text: label.$2,
          style: TextStyle(color: labelColor, fontSize: 9.5),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      final labelX = (x(label.$1) - painter.width / 2).clamp(
        0.0,
        size.width - painter.width,
      );
      painter.paint(canvas, Offset(labelX, size.height - painter.height));
    }
  }

  void _drawDashedLine(Canvas canvas, Offset start, Offset end, Paint paint) {
    final vector = end - start;
    final distance = vector.distance;
    if (distance == 0) return;
    final direction = vector / distance;
    const dash = 7.0;
    const gap = 5.0;
    for (var offset = 0.0; offset < distance; offset += dash + gap) {
      canvas.drawLine(
        start + direction * offset,
        start + direction * (offset + dash).clamp(0, distance),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _GoalTrendPainter oldDelegate) {
    return range != oldDelegate.range ||
        actualCents != oldDelegate.actualCents ||
        targetCents != oldDelegate.targetCents ||
        projectedCents != oldDelegate.projectedCents ||
        elapsedFraction != oldDelegate.elapsedFraction ||
        actualColor != oldDelegate.actualColor ||
        goalColor != oldDelegate.goalColor ||
        gridColor != oldDelegate.gridColor ||
        labelColor != oldDelegate.labelColor;
  }
}

class _MonthlyGoalPanel extends StatefulWidget {
  const _MonthlyGoalPanel({
    required this.monthlyGoalCents,
    required this.onSave,
  });

  final int monthlyGoalCents;
  final Future<void> Function(int monthlyGoalCents) onSave;

  @override
  State<_MonthlyGoalPanel> createState() => _MonthlyGoalPanelState();
}

class _MonthlyGoalPanelState extends State<_MonthlyGoalPanel> {
  late final TextEditingController _controller = TextEditingController(
    text: _dollarsInput(widget.monthlyGoalCents),
  );
  bool _saving = false;
  String? _error;
  String? _success;

  @override
  void didUpdateWidget(covariant _MonthlyGoalPanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.monthlyGoalCents != widget.monthlyGoalCents) {
      _controller.text = _dollarsInput(widget.monthlyGoalCents);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final monthlyGoalCents = _parseMoneyToCents(_controller.text);
    if (monthlyGoalCents == null || monthlyGoalCents <= 0) {
      setState(() {
        _error = 'Enter a monthly goal greater than zero.';
        _success = null;
      });
      return;
    }

    setState(() {
      _saving = true;
      _error = null;
      _success = null;
    });
    try {
      await widget.onSave(monthlyGoalCents);
      if (!mounted) return;
      setState(() {
        _success = 'Goal saved.';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
      });
    } finally {
      if (mounted) {
        setState(() {
          _saving = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return _Panel(
      padding: const EdgeInsets.all(14),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 330;

          return Wrap(
            spacing: 10,
            runSpacing: 12,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              SizedBox(
                width: compact ? constraints.maxWidth : 190,
                child: Text(
                  'Adjust Monthly Goal',
                  style: TextStyle(
                    color: context.appInk,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              SizedBox(
                width: compact ? constraints.maxWidth - 106 : 190,
                height: 48,
                child: TextField(
                  controller: _controller,
                  enabled: !_saving,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  inputFormatters: [
                    FilteringTextInputFormatter.allow(
                      RegExp(r'^\d*\.?\d{0,2}'),
                    ),
                  ],
                  decoration: InputDecoration(
                    labelText: 'Monthly income goal',
                    floatingLabelBehavior: FloatingLabelBehavior.always,
                    prefixText: '\$ ',
                    filled: true,
                    fillColor: context.appSoftFill,
                    isDense: true,
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 14,
                    ),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                  ),
                ),
              ),
              Container(
                key: const ValueKey('monthly-goal-save-button-box'),
                height: 48,
                width: 96,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF36BDB5), Color(0xFF078A83)],
                  ),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: FilledButton(
                  onPressed: _saving ? null : _save,
                  style: FilledButton.styleFrom(
                    backgroundColor: Colors.transparent,
                    disabledBackgroundColor: Colors.transparent,
                    shadowColor: Colors.transparent,
                    minimumSize: Size.zero,
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                  ),
                  child: _saving
                      ? const SizedBox.square(
                          dimension: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Text('Save'),
                ),
              ),
              if (_error != null)
                SizedBox(
                  width: constraints.maxWidth,
                  child: Text(
                    _error!,
                    style: const TextStyle(color: Color(0xFFB91C1C)),
                  ),
                ),
              if (_success != null)
                SizedBox(
                  width: constraints.maxWidth,
                  child: Text(
                    _success!,
                    style: const TextStyle(
                      color: Color(0xFF15803D),
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _PacingPanel extends StatelessWidget {
  const _PacingPanel({required this.goal});

  final GoalSnapshot goal;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: context.isDarkMode
            ? const Color(0xFF102A35)
            : const Color(0xFFECF9F8),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: context.isDarkMode
              ? const Color(0xFF28515B)
              : const Color(0xFFD2EFEC),
        ),
        boxShadow: context.appCardShadows,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: const BoxDecoration(
              color: Color(0xFFD7F2EF),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.timer_outlined,
              color: Color(0xFF2BAFA8),
              size: 21,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Pacing tip',
                  style: TextStyle(
                    color: context.appInk,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  goal.pacingMessage,
                  style: TextStyle(color: context.appMuted),
                ),
                if (goal.recommendedMonthlyLeads > 0) ...[
                  const SizedBox(height: 6),
                  Text(
                    '${goal.recommendedMonthlyLeads} leads recommended per month',
                    style: TextStyle(
                      color: const Color(0xFF2BAFA8),
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.value,
    required this.label,
    required this.icon,
  });

  final String value;
  final String label;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  value,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Color(0xFF2BAFA8),
                    fontSize: 23,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              Icon(
                icon,
                color: context.appMuted.withValues(alpha: 0.45),
                size: 19,
              ),
            ],
          ),
          const Spacer(),
          Text(
            label,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: context.appMuted,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _PackagePreview extends StatelessWidget {
  const _PackagePreview({required this.package, required this.onSelect});

  final LeadPackage package;
  final VoidCallback onSelect;

  @override
  Widget build(BuildContext context) {
    final badge = _packageBadge(package);

    return SizedBox(
      width: 210,
      child: _Panel(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  _packageIcon(package.name),
                  color: const Color(0xFF2BAFA8),
                  size: 20,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    package.name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: context.appInk,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
              ],
            ),
            if (badge != null) ...[
              const SizedBox(height: 5),
              _TinyBadge(label: badge),
            ],
            const SizedBox(height: 9),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  _money(package.priceCents),
                  style: TextStyle(
                    color: context.appInk,
                    fontSize: 28,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text(
                    ' / MO',
                    style: TextStyle(
                      color: context.appMuted,
                      fontSize: 10,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 2),
            Text(
              '${package.creditsTotal} leads · ${_money(package.costPerLeadCents)}/lead',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: context.appMuted, fontSize: 12),
            ),
            const Spacer(),
            Container(
              height: 38,
              width: double.infinity,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF36BDB5), Color(0xFF078A83)],
                ),
                borderRadius: BorderRadius.circular(12),
              ),
              child: FilledButton(
                onPressed: onSelect,
                style: FilledButton.styleFrom(
                  backgroundColor: Colors.transparent,
                  shadowColor: Colors.transparent,
                  minimumSize: Size.zero,
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text('Select'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TinyBadge extends StatelessWidget {
  const _TinyBadge({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(maxWidth: 64),
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
      decoration: BoxDecoration(
        color: const Color(0xFFE8FBFF),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: const TextStyle(
          color: Color(0xFF18A0B8),
          fontSize: 9,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _Panel extends StatelessWidget {
  const _Panel({required this.child, this.padding = const EdgeInsets.all(14)});

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(padding: padding, child: child),
    );
  }
}

String? _packageBadge(LeadPackage package) {
  final name = package.name.toLowerCase();
  if (name.contains('pro')) return 'Best Value';
  if (name.contains('elite') || name.contains('unlimited')) return 'Most Leads';
  return null;
}

IconData _packageIcon(String name) {
  final normalized = name.toLowerCase();
  if (normalized.contains('unlimited') || normalized.contains('elite')) {
    return Icons.bolt_outlined;
  }
  if (normalized.contains('pro')) return Icons.star_border_rounded;
  return Icons.inventory_2_outlined;
}

String _money(int cents) => '\$${(cents / 100).round()}';

String _dollarsInput(int cents) {
  final dollars = cents / 100;
  return dollars == dollars.roundToDouble()
      ? dollars.toStringAsFixed(0)
      : dollars.toStringAsFixed(2);
}

int? _parseMoneyToCents(String value) {
  final normalized = value.trim().replaceAll(',', '');
  final dollars = double.tryParse(normalized);
  if (dollars == null || !dollars.isFinite) return null;
  return (dollars * 100).round();
}
