import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/screens/advisor/lead_details_sheet.dart';
import 'package:flutter_frontend/theme/app_components.dart';
import 'package:flutter_frontend/theme/app_theme.dart';

class GoalsScreen extends StatefulWidget {
  const GoalsScreen({
    super.key,
    required this.onSeeAllPackages,
    this.repository,
    this.outcomeRevision,
  });

  final ValueChanged<int?> onSeeAllPackages;
  final AdvisorRepository? repository;
  final Listenable? outcomeRevision;

  @override
  State<GoalsScreen> createState() => _GoalsScreenState();
}

class _GoalsScreenState extends State<GoalsScreen> {
  late final AdvisorRepository _repository =
      widget.repository ?? AdvisorRepository();
  late Future<GoalSnapshot> _future = _repository.getGoal();
  GoalSnapshot? _savedGoal;

  @override
  void initState() {
    super.initState();
    widget.outcomeRevision?.addListener(_retry);
  }

  @override
  void didUpdateWidget(covariant GoalsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.outcomeRevision == widget.outcomeRevision) return;
    oldWidget.outcomeRevision?.removeListener(_retry);
    widget.outcomeRevision?.addListener(_retry);
  }

  @override
  void dispose() {
    widget.outcomeRevision?.removeListener(_retry);
    super.dispose();
  }

  void _retry() {
    _refreshGoals();
  }

  Future<void> _refreshGoals() async {
    final future = _repository.getGoal();
    setState(() {
      _savedGoal = null;
      _future = future;
    });
    await future;
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

  Future<void> _openLead(AdvisorLead lead) {
    return showLeadDetailsSheet(
      context: context,
      lead: lead,
      repository: _repository,
      onUpdated: (_) => _refreshGoals(),
    );
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<GoalSnapshot>(
      future: _future,
      builder: (context, snapshot) {
        final goal = _savedGoal ?? snapshot.data;
        return AppRefreshIndicator(
          onRefresh: _refreshGoals,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 112),
            children: [
              const AppScreenHeader(
                eyebrow: 'Performance plan',
                title: 'Goals',
                subtitle: 'Track your annual target and next best actions.',
                icon: Icons.track_changes_rounded,
              ),
              const SizedBox(height: 12),
              if (snapshot.connectionState == ConnectionState.waiting &&
                  goal == null)
                const Center(
                  child: AppLoadingIndicator(label: 'Loading goal plan'),
                )
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
                _GoalHero(
                  goal: goal!,
                  monthlyGoalEditor: _MonthlyGoalPanel(
                    embedded: true,
                    monthlyGoalCents: (goal.annualGoalCents / 12).round(),
                    onSave: (monthlyGoalCents) =>
                        _saveMonthlyGoal(goal, monthlyGoalCents),
                  ),
                ),
                const SizedBox(height: 10),
                GridView.count(
                  crossAxisCount: 2,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  crossAxisSpacing: 12,
                  mainAxisSpacing: 12,
                  mainAxisExtent: 92,
                  children: [
                    _StatCard(
                      value: '${goal.dealsRemaining}',
                      label: 'Deals Remaining',
                      icon: Icons.emoji_events_outlined,
                      accent: Color(0xFFD58416),
                      lightSurface: Color(0xFFFFF8E8),
                      darkSurface: Color(0xFF2A2113),
                      detail: 'Income gap divided by your average commission.',
                      recordsTitle: 'Recently closed deals',
                      loadRecords: () async => (await _repository.getLeadsPage(
                        size: 100,
                        outcomeStatus: 'closed_deal',
                      )).items,
                      onLeadTap: _openLead,
                    ),
                    _StatCard(
                      value: '${goal.appointmentsRemaining}',
                      label: 'Appointments Remaining',
                      icon: Icons.calendar_today_outlined,
                      accent: Color(0xFF5967D8),
                      lightSurface: Color(0xFFF1F3FF),
                      darkSurface: Color(0xFF1C2341),
                      detail: 'Deals remaining adjusted by your closing rate.',
                      recordsTitle: 'Appointments awaiting follow-up',
                      loadRecords: () async => (await _repository.getLeadsPage(
                        size: 100,
                        outcomeStatus: 'appointment_set',
                      )).items,
                      onLeadTap: _openLead,
                    ),
                    _StatCard(
                      value: '${goal.leadsRemaining}',
                      label: 'Leads Remaining',
                      icon: Icons.group_outlined,
                      accent: Color(0xFF0F9F98),
                      lightSurface: Color(0xFFEAFBF8),
                      darkSurface: Color(0xFF102C2B),
                      detail:
                          'Appointments needed adjusted by lead conversion.',
                      recordsTitle: 'Active leads in your pipeline',
                      loadRecords: () async =>
                          (await _repository.getLeadsPage(size: 100)).items,
                      onLeadTap: _openLead,
                    ),
                    _StatCard(
                      value: '${goal.closedDealsYtd}',
                      label: 'Closed YTD',
                      icon: Icons.check_circle_outline_rounded,
                      accent: Color(0xFF168A5B),
                      lightSurface: Color(0xFFEBFAF2),
                      darkSurface: Color(0xFF112B20),
                      detail: 'Leads marked Closed Deal this target year.',
                      recordsTitle: 'Deals closed this year',
                      loadRecords: () async => (await _repository.getLeadsPage(
                        size: 100,
                        outcomeStatus: 'closed_deal',
                      )).items,
                      onLeadTap: _openLead,
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                _SuccessRateCard(goal: goal),
                const SizedBox(height: 10),
                _GoalTrendCard(goal: goal),
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
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    TextButton(
                      onPressed: () => widget.onSeeAllPackages(null),
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
                        onSelect: () =>
                            widget.onSeeAllPackages(goal.packages[index].id),
                      ),
                    ),
                  ),
              ],
            ],
          ),
        );
      },
    );
  }
}

class _SuccessRateCard extends StatelessWidget {
  const _SuccessRateCard({required this.goal});

  final GoalSnapshot goal;

  @override
  Widget build(BuildContext context) {
    final hasActivity = goal.reachedLeadsYtd > 0;
    final onTarget =
        hasActivity &&
        goal.currentSuccessRateBps >= goal.appointmentToDealRateBps;
    final accent = onTarget ? const Color(0xFF0F9F82) : const Color(0xFFD58416);
    final targetProgress = goal.appointmentToDealRateBps <= 0
        ? 0.0
        : (goal.currentSuccessRateBps / goal.appointmentToDealRateBps).clamp(
            0.0,
            1.0,
          );

    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: context.isDarkMode
              ? [const Color(0xFF171717), accent.withValues(alpha: .12)]
              : [Colors.white, accent.withValues(alpha: .08)],
        ),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: accent.withValues(alpha: .28)),
        boxShadow: context.appCardShadows,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: .13),
                  borderRadius: BorderRadius.circular(11),
                ),
                child: Icon(Icons.insights_rounded, color: accent, size: 20),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Conversion success',
                      style: TextStyle(
                        color: context.appInk,
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    Text(
                      'Closed deals compared with leads you reached.',
                      style: TextStyle(color: context.appMuted, fontSize: 10.5),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: .12),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  !hasActivity
                      ? 'No activity yet'
                      : onTarget
                      ? 'On target'
                      : 'Below target',
                  style: TextStyle(
                    color: accent,
                    fontSize: 9.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _RateMetric(
                  label: 'SET SUCCESS RATE',
                  value: _formatRate(goal.appointmentToDealRateBps),
                  caption: 'Your planned close rate',
                  color: const Color(0xFF5967D8),
                ),
              ),
              Container(width: 1, height: 48, color: context.appOutline),
              Expanded(
                child: _RateMetric(
                  label: 'CURRENT SUCCESS RATE',
                  value: _formatRate(goal.currentSuccessRateBps),
                  caption:
                      '${goal.closedDealsYtd} of ${goal.reachedLeadsYtd} reached',
                  color: accent,
                ),
              ),
            ],
          ),
          const SizedBox(height: 13),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              minHeight: 7,
              value: targetProgress,
              backgroundColor: context.appOutline.withValues(alpha: .55),
              valueColor: AlwaysStoppedAnimation(accent),
            ),
          ),
          const SizedBox(height: 9),
          Row(
            children: [
              Icon(
                Icons.info_outline_rounded,
                color: context.appMuted,
                size: 15,
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  '${goal.contactedLeadsYtd} contacted • '
                  '${goal.appointmentsSetYtd} appointment set • '
                  '${goal.closedDealsYtd} closed',
                  style: TextStyle(
                    color: context.appMuted,
                    fontSize: 10.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _RateMetric extends StatelessWidget {
  const _RateMetric({
    required this.label,
    required this.value,
    required this.caption,
    required this.color,
  });

  final String label;
  final String value;
  final String caption;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(
              color: context.appMuted,
              fontSize: 9,
              fontWeight: FontWeight.w700,
              letterSpacing: .7,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 22,
              fontWeight: FontWeight.w700,
              letterSpacing: -.5,
            ),
          ),
          Text(
            caption,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(color: context.appMuted, fontSize: 9.5),
          ),
        ],
      ),
    );
  }
}

String _formatRate(int basisPoints) {
  final percentage = basisPoints / 100;
  return percentage == percentage.roundToDouble()
      ? '${percentage.round()}%'
      : '${percentage.toStringAsFixed(1)}%';
}

class _GoalHero extends StatelessWidget {
  const _GoalHero({required this.goal, required this.monthlyGoalEditor});

  final GoalSnapshot goal;
  final Widget monthlyGoalEditor;

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
                          fontWeight: FontWeight.w700,
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
                          fontWeight: FontWeight.w700,
                          fontFeatures: [FontFeature.tabularFigures()],
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
                          fontWeight: FontWeight.w700,
                          fontFeatures: [FontFeature.tabularFigures()],
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            monthlyGoalEditor,
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
  int? _selectedPointIndex;

  void _selectPoint(Offset position, double width, double elapsedFraction) {
    final history = _trendHistory(_range);
    final usableWidth = (width - 8) * elapsedFraction.clamp(0.01, 1.0);
    final fraction = ((position.dx - 4) / usableWidth).clamp(0.0, 1.0);
    final index = (fraction * (history.length - 1)).round();
    if (_selectedPointIndex != index) {
      setState(() => _selectedPointIndex = index);
    }
  }

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
    final selectedIndex = _selectedPointIndex;
    final selectedEarnings = selectedIndex == null
        ? null
        : (demoActualCents * _trendHistory(_range)[selectedIndex]).round();

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
                        fontWeight: FontWeight.w700,
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
            onSelected: (range) => setState(() {
              _range = range;
              _selectedPointIndex = null;
            }),
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
                'Visualized ${_money(demoActualCents)}.'
                '${selectedIndex == null || selectedEarnings == null ? '' : ' Selected ${_trendPointLabel(_range, selectedIndex, chartElapsed)}, earnings ${_money(selectedEarnings)}.'}',
            hint: 'Tap or drag across the graph to inspect an earnings point.',
            child: SizedBox(
              height: 174,
              width: double.infinity,
              child: LayoutBuilder(
                builder: (context, constraints) => GestureDetector(
                  key: const ValueKey('goal-trend-interaction'),
                  behavior: HitTestBehavior.opaque,
                  onTapDown: (details) => _selectPoint(
                    details.localPosition,
                    constraints.maxWidth,
                    chartElapsed,
                  ),
                  onHorizontalDragStart: (details) => _selectPoint(
                    details.localPosition,
                    constraints.maxWidth,
                    chartElapsed,
                  ),
                  onHorizontalDragUpdate: (details) => _selectPoint(
                    details.localPosition,
                    constraints.maxWidth,
                    chartElapsed,
                  ),
                  child: CustomPaint(
                    painter: _GoalTrendPainter(
                      range: _range,
                      actualCents: demoActualCents,
                      targetCents: targetCents,
                      projectedCents: chartProjected,
                      elapsedFraction: chartElapsed,
                      selectedPointIndex: selectedIndex,
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
                          fontWeight: FontWeight.w700,
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
              fontWeight: FontWeight.w700,
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
            fontWeight: FontWeight.w700,
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

List<double> _trendHistory(_TrendRange range) {
  return switch (range) {
    _TrendRange.sevenDays => const [0.08, 0.24, 0.24, 0.48, 0.63, 0.63, 1.0],
    _TrendRange.month => const [0.07, 0.22, 0.22, 0.39, 0.58, 0.58, 0.82, 1.0],
    _TrendRange.year => const [
      0.0,
      0.09,
      0.16,
      0.16,
      0.31,
      0.43,
      0.43,
      0.60,
      0.70,
      0.70,
      0.86,
      1.0,
    ],
  };
}

String _trendPointLabel(_TrendRange range, int index, double elapsedFraction) {
  const months = [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
  ];
  return switch (range) {
    _TrendRange.sevenDays => index == 6 ? 'Today' : '${6 - index} days ago',
    _TrendRange.month => 'Period ${index + 1} of 8',
    _TrendRange.year =>
      months[((index / (_trendHistory(range).length - 1)) *
              elapsedFraction.clamp(0.0, 1.0) *
              months.length)
          .floor()
          .clamp(0, months.length - 1)],
  };
}

class _GoalTrendPainter extends CustomPainter {
  const _GoalTrendPainter({
    required this.range,
    required this.actualCents,
    required this.targetCents,
    required this.projectedCents,
    required this.elapsedFraction,
    required this.selectedPointIndex,
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
  final int? selectedPointIndex;
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
    final history = _trendHistory(range);
    final demoPoints = <Offset>[
      for (var index = 0; index < history.length; index++)
        Offset(
          x(currentX * index / (history.length - 1)),
          y(actualCents * history[index]),
        ),
    ];
    final demoPath = Path()..moveTo(demoPoints.first.dx, demoPoints.first.dy);
    _addSmoothCurve(demoPath, demoPoints);
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

    final selectedIndex = selectedPointIndex;
    if (selectedIndex != null &&
        selectedIndex >= 0 &&
        selectedIndex < demoPoints.length) {
      final selectedPoint = demoPoints[selectedIndex];
      final guidePaint = Paint()
        ..color = actualColor.withValues(alpha: .32)
        ..strokeWidth = 1.2;
      canvas.drawLine(
        Offset(selectedPoint.dx, top),
        Offset(selectedPoint.dx, top + chartHeight),
        guidePaint,
      );
      canvas.drawCircle(
        selectedPoint,
        8,
        Paint()..color = actualColor.withValues(alpha: .18),
      );
      canvas.drawCircle(selectedPoint, 4.5, Paint()..color = actualColor);
      canvas.drawCircle(selectedPoint, 2, Paint()..color = Colors.white);
      _drawSelectionTooltip(
        canvas,
        size,
        selectedPoint,
        selectedIndex,
        top,
        chartHeight,
      );
    }
  }

  void _drawSelectionTooltip(
    Canvas canvas,
    Size size,
    Offset point,
    int pointIndex,
    double chartTop,
    double chartHeight,
  ) {
    final period = _trendPointLabel(range, pointIndex, elapsedFraction);
    final earnings = (actualCents * _trendHistory(range)[pointIndex]).round();
    final textPainter = TextPainter(
      text: TextSpan(
        children: [
          TextSpan(
            text: period,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 9.5,
              fontWeight: FontWeight.w700,
            ),
          ),
          TextSpan(
            text: '\n${_money(earnings)}',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 11,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
      textDirection: TextDirection.ltr,
    )..layout(minWidth: 66, maxWidth: 96);
    final bubbleSize = Size(textPainter.width + 16, textPainter.height + 10);
    final placeRight = point.dx + 10 + bubbleSize.width <= size.width - 4;
    final bubbleLeft = placeRight
        ? point.dx + 10
        : point.dx - 10 - bubbleSize.width;
    final bubbleTop = (point.dy - bubbleSize.height / 2).clamp(
      chartTop,
      chartTop + chartHeight - bubbleSize.height,
    );
    final bubbleRect = Rect.fromLTWH(
      bubbleLeft,
      bubbleTop,
      bubbleSize.width,
      bubbleSize.height,
    );
    final bubbleRRect = RRect.fromRectAndRadius(
      bubbleRect,
      const Radius.circular(8),
    );
    final bubblePath = Path()..addRRect(bubbleRRect);
    canvas.drawShadow(
      bubblePath,
      Colors.black.withValues(alpha: .28),
      4,
      false,
    );
    final bubblePaint = Paint()..color = actualColor;
    canvas.drawRRect(bubbleRRect, bubblePaint);
    final pointerCenterY = bubbleRect.center.dy.clamp(
      bubbleRect.top + 7,
      bubbleRect.bottom - 7,
    );
    final pointerPath = Path()..moveTo(point.dx, point.dy);
    if (placeRight) {
      pointerPath
        ..lineTo(bubbleRect.left, pointerCenterY - 5)
        ..lineTo(bubbleRect.left, pointerCenterY + 5);
    } else {
      pointerPath
        ..lineTo(bubbleRect.right, pointerCenterY - 5)
        ..lineTo(bubbleRect.right, pointerCenterY + 5);
    }
    pointerPath.close();
    canvas.drawPath(pointerPath, bubblePaint);
    textPainter.paint(canvas, Offset(bubbleRect.left + 8, bubbleRect.top + 5));
  }

  void _addSmoothCurve(Path path, List<Offset> points) {
    if (points.length < 2) return;

    // Earnings are cumulative. Horizontal cubic controls produce a smooth,
    // monotonic transition inside every segment, including genuinely flat
    // periods, without inventing a temporary drop between data points.
    for (var index = 0; index < points.length - 1; index++) {
      final current = points[index];
      final next = points[index + 1];
      final middleX = (current.dx + next.dx) / 2;
      path.cubicTo(middleX, current.dy, middleX, next.dy, next.dx, next.dy);
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
        selectedPointIndex != oldDelegate.selectedPointIndex ||
        actualColor != oldDelegate.actualColor ||
        goalColor != oldDelegate.goalColor ||
        gridColor != oldDelegate.gridColor ||
        labelColor != oldDelegate.labelColor;
  }
}

class _MonthlyGoalPanel extends StatefulWidget {
  const _MonthlyGoalPanel({
    this.embedded = false,
    required this.monthlyGoalCents,
    required this.onSave,
  });

  final bool embedded;
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
  bool _editing = false;
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
        _editing = false;
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
    final foreground = widget.embedded ? Colors.white : context.appInk;
    final muted = widget.embedded ? Colors.white70 : context.appMuted;
    if (!_editing) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
        decoration: BoxDecoration(
          color: widget.embedded
              ? Colors.white.withValues(alpha: .08)
              : context.appSoftFill,
          borderRadius: BorderRadius.circular(13),
          border: Border.all(
            color: widget.embedded ? Colors.white24 : context.appOutline,
          ),
        ),
        child: Row(
          children: [
            Icon(Icons.tune_rounded, color: muted, size: 17),
            const SizedBox(width: 8),
            Text('Monthly goal', style: TextStyle(color: muted, fontSize: 11)),
            const Spacer(),
            Text(
              _money(widget.monthlyGoalCents),
              style: TextStyle(
                color: foreground,
                fontSize: 15,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(width: 8),
            TextButton(
              key: const ValueKey('monthly-goal-adjust-button'),
              onPressed: () => setState(() => _editing = true),
              style: TextButton.styleFrom(
                foregroundColor: widget.embedded
                    ? const Color(0xFF70E5EA)
                    : const Color(0xFF0F9F98),
                padding: const EdgeInsets.symmetric(horizontal: 9),
                minimumSize: const Size(0, 32),
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
              child: const Text('Update'),
            ),
          ],
        ),
      );
    }
    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'Monthly goal',
                style: TextStyle(
                  color: foreground,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            Text(
              'Updates annual target',
              style: TextStyle(color: muted, fontSize: 9),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: SizedBox(
                height: 42,
                child: TextField(
                  controller: _controller,
                  enabled: !_saving,
                  style: TextStyle(
                    color: foreground,
                    fontWeight: FontWeight.w600,
                  ),
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
                    labelStyle: TextStyle(color: muted),
                    floatingLabelBehavior: FloatingLabelBehavior.always,
                    prefixText: '\$ ',
                    prefixStyle: TextStyle(color: foreground),
                    filled: true,
                    fillColor: widget.embedded
                        ? Colors.white.withValues(alpha: .12)
                        : context.appSoftFill,
                    isDense: true,
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 13,
                      vertical: 13,
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(13),
                      borderSide: BorderSide(
                        color: widget.embedded
                            ? Colors.white30
                            : context.appOutline,
                      ),
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Container(
              key: const ValueKey('monthly-goal-save-button-box'),
              height: 42,
              width: 76,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF42D3C8), Color(0xFF07958D)],
                ),
                borderRadius: BorderRadius.circular(13),
              ),
              child: FilledButton(
                onPressed: _saving ? null : _save,
                style: FilledButton.styleFrom(
                  backgroundColor: Colors.transparent,
                  disabledBackgroundColor: Colors.transparent,
                  shadowColor: Colors.transparent,
                  minimumSize: Size.zero,
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                ),
                child: _saving
                    ? const AppLoadingIndicator(compact: true)
                    : const Text('Save'),
              ),
            ),
          ],
        ),
        if (_error != null) ...[
          const SizedBox(height: 7),
          Text(
            _error!,
            style: TextStyle(
              color: widget.embedded
                  ? const Color(0xFFFFD0D6)
                  : const Color(0xFFB91C1C),
              fontSize: 11,
            ),
          ),
        ],
        if (_success != null) ...[
          const SizedBox(height: 7),
          Text(
            _success!,
            style: TextStyle(
              color: widget.embedded
                  ? const Color(0xFFB8FFE1)
                  : const Color(0xFF15803D),
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ],
    );
    if (!widget.embedded) {
      return _Panel(padding: const EdgeInsets.all(14), child: content);
    }
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: .08),
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: Colors.white24),
      ),
      child: content,
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
                    fontWeight: FontWeight.w700,
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
                      fontWeight: FontWeight.w700,
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
    required this.accent,
    required this.lightSurface,
    required this.darkSurface,
    required this.detail,
    required this.recordsTitle,
    required this.loadRecords,
    required this.onLeadTap,
  });

  final String value;
  final String label;
  final IconData icon;
  final Color accent;
  final Color lightSurface;
  final Color darkSurface;
  final String detail;
  final String recordsTitle;
  final Future<List<AdvisorLead>> Function() loadRecords;
  final ValueChanged<AdvisorLead> onLeadTap;

  void _showDetails(BuildContext context) {
    final records = loadRecords();
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: accent.withValues(alpha: .13),
                      borderRadius: BorderRadius.circular(13),
                    ),
                    child: Icon(icon, color: accent),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          value,
                          style: TextStyle(
                            color: accent,
                            fontSize: 25,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        Text(
                          label,
                          style: TextStyle(
                            color: context.appInk,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Text(
                recordsTitle,
                style: TextStyle(
                  color: context.appInk,
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 8),
              FutureBuilder<List<AdvisorLead>>(
                future: records,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Padding(
                      padding: EdgeInsets.symmetric(vertical: 12),
                      child: AppLoadingIndicator(
                        compact: true,
                        label: 'Loading activity',
                      ),
                    );
                  }
                  final leads = snapshot.data ?? const <AdvisorLead>[];
                  if (snapshot.hasError || leads.isEmpty) {
                    return Text(
                      snapshot.hasError
                          ? 'Activity could not be loaded right now.'
                          : 'No matching activity yet.',
                      style: TextStyle(color: context.appMuted, fontSize: 12),
                    );
                  }
                  return ConstrainedBox(
                    constraints: BoxConstraints(
                      maxHeight: MediaQuery.sizeOf(context).height * .55,
                    ),
                    child: ListView.separated(
                      shrinkWrap: true,
                      itemCount: leads.length,
                      separatorBuilder: (_, _) =>
                          Divider(height: 1, color: context.appOutline),
                      itemBuilder: (context, index) {
                        final lead = leads[index];
                        final status = switch (lead.outcomeStatus) {
                          'closed_deal' => 'Closed deal',
                          'appointment_set' => 'Appointment set',
                          'contacted' => 'Contacted',
                          _ => 'New lead',
                        };
                        return ListTile(
                          onTap: () {
                            Navigator.of(context).pop();
                            WidgetsBinding.instance.addPostFrameCallback(
                              (_) => onLeadTap(lead),
                            );
                          },
                          dense: true,
                          contentPadding: EdgeInsets.zero,
                          leading: CircleAvatar(
                            radius: 16,
                            backgroundColor: accent.withValues(alpha: .14),
                            foregroundColor: accent,
                            child: Text(
                              lead.displayName.isEmpty
                                  ? 'L'
                                  : lead.displayName.substring(0, 1),
                              style: const TextStyle(fontSize: 12),
                            ),
                          ),
                          title: Text(
                            lead.displayName,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 12.5,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          subtitle: Text(
                            '${lead.stateCode}  •  $status',
                            style: TextStyle(
                              color: context.appMuted,
                              fontSize: 10.5,
                            ),
                          ),
                          trailing: const Icon(
                            Icons.chevron_right_rounded,
                            size: 19,
                          ),
                        );
                      },
                    ),
                  );
                },
              ),
              const SizedBox(height: 12),
              Divider(height: 1, color: context.appOutline),
              const SizedBox(height: 10),
              Text(
                'Calculation',
                style: TextStyle(
                  color: context.appInk,
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 3),
              Text(
                detail,
                style: TextStyle(color: context.appMuted, fontSize: 11),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final surface = context.isDarkMode ? darkSurface : lightSurface;
    final displayAccent = context.isDarkMode
        ? Color.lerp(accent, Colors.white, 0.14)!
        : accent;

    return Semantics(
      button: true,
      label: '$label, $value. Tap for details.',
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => _showDetails(context),
          borderRadius: BorderRadius.circular(17),
          child: Ink(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  surface,
                  Color.lerp(surface, context.appSurface, 0.42)!,
                ],
              ),
              borderRadius: BorderRadius.circular(17),
              border: Border.all(color: displayAccent.withValues(alpha: 0.2)),
              boxShadow: context.appCardShadows,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 28,
                      height: 28,
                      decoration: BoxDecoration(
                        color: displayAccent.withValues(
                          alpha: context.isDarkMode ? 0.18 : 0.12,
                        ),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(icon, color: displayAccent, size: 17),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      value,
                      maxLines: 1,
                      style: TextStyle(
                        color: displayAccent,
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                        fontFeatures: const [FontFeature.tabularFigures()],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 5),
                SizedBox(
                  height: 27,
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Text(
                          label,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            color: context.appMuted,
                            fontSize: 11,
                            height: 1.15,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      Icon(
                        Icons.info_outline_rounded,
                        size: 13,
                        color: displayAccent,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
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
                      fontWeight: FontWeight.w700,
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
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text(
                    ' / MO',
                    style: TextStyle(
                      color: context.appMuted,
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
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
          fontWeight: FontWeight.w700,
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

String _money(int cents) => '\$${_groupDigits((cents / 100).round())}';

String _groupDigits(int value) {
  final digits = value.abs().toString();
  final grouped = digits.replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'),
    (_) => ',',
  );
  return value < 0 ? '-$grouped' : grouped;
}

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
