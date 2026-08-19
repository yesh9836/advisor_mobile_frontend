import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';

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
          padding: const EdgeInsets.fromLTRB(16, 20, 16, 24),
          children: [
            const Text(
              'Goals',
              style: TextStyle(
                color: Color(0xFF202860),
                fontSize: 22,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 18),
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
              const SizedBox(height: 12),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                childAspectRatio: 1.55,
                children: [
                  _StatCard(
                    value: '${goal.dealsRemaining}',
                    label: 'Deals Remaining',
                  ),
                  _StatCard(
                    value: '${goal.appointmentsRemaining}',
                    label: 'Appointments Remaining',
                  ),
                  _StatCard(
                    value: '${goal.leadsRemaining}',
                    label: 'Leads Remaining',
                  ),
                  _StatCard(
                    value: '${goal.closedDealsYtd}',
                    label: 'Closed YTD',
                  ),
                ],
              ),
              const SizedBox(height: 14),
              _MonthlyGoalPanel(
                monthlyGoalCents: (goal.annualGoalCents / 12).round(),
                onSave: (monthlyGoalCents) =>
                    _saveMonthlyGoal(goal, monthlyGoalCents),
              ),
              if (goal.pacingMessage.isNotEmpty) ...[
                const SizedBox(height: 12),
                _PacingPanel(goal: goal),
              ],
              const SizedBox(height: 18),
              Row(
                children: [
                  const Expanded(
                    child: Text(
                      'Recommended Packages',
                      style: TextStyle(
                        color: Color(0xFF202860),
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
                  height: 172,
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
        padding: const EdgeInsets.all(20),
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
                  width: 108,
                  height: 108,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      SizedBox.expand(
                        child: CircularProgressIndicator(
                          value: progress,
                          strokeWidth: 10,
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
                const SizedBox(width: 22),
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
                          fontSize: 26,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(height: 14),
                      const Text(
                        'Target',
                        style: TextStyle(color: Colors.white70),
                      ),
                      Text(
                        _money(goal.annualGoalCents),
                        style: const TextStyle(
                          color: Color(0xFF7DD3FC),
                          fontSize: 20,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
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
      padding: const EdgeInsets.all(16),
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
                child: const Text(
                  'Adjust Monthly Goal',
                  style: TextStyle(
                    color: Color(0xFF202860),
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              SizedBox(
                width: compact ? constraints.maxWidth - 86 : 190,
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
                    fillColor: const Color(0xFFF7FBFD),
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
              SizedBox(
                key: const ValueKey('monthly-goal-save-button-box'),
                height: 48,
                width: 76,
                child: FilledButton(
                  onPressed: _saving ? null : _save,
                  style: FilledButton.styleFrom(
                    minimumSize: Size.zero,
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
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
    return _Panel(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.speed, color: Color(0xFF18A0B8)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Pacing tip',
                  style: TextStyle(
                    color: Color(0xFF202860),
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  goal.pacingMessage,
                  style: const TextStyle(color: Color(0xFF58707D)),
                ),
                if (goal.recommendedMonthlyLeads > 0) ...[
                  const SizedBox(height: 6),
                  Text(
                    '${goal.recommendedMonthlyLeads} leads recommended per month',
                    style: const TextStyle(
                      color: Color(0xFF202860),
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
  const _StatCard({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: Color(0xFF18A0B8),
              fontSize: 22,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            label,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: Color(0xFF202860),
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
      width: 156,
      child: _Panel(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    package.name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Color(0xFF202860),
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
                if (badge != null) _TinyBadge(label: badge),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              _money(package.priceCents),
              style: const TextStyle(
                color: Color(0xFF202860),
                fontSize: 24,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              '${package.creditsTotal} leads · ${_money(package.costPerLeadCents)}/lead',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: Color(0xFF58707D), fontSize: 12),
            ),
            const Spacer(),
            SizedBox(
              height: 38,
              width: double.infinity,
              child: FilledButton(
                onPressed: onSelect,
                style: FilledButton.styleFrom(
                  minimumSize: Size.zero,
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
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
  const _Panel({required this.child, this.padding = const EdgeInsets.all(16)});

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
