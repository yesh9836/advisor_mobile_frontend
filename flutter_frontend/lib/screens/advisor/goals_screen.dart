import 'package:flutter/material.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';

class GoalsScreen extends StatefulWidget {
  const GoalsScreen({super.key, required this.onSeeAllPackages});

  final VoidCallback onSeeAllPackages;

  @override
  State<GoalsScreen> createState() => _GoalsScreenState();
}

class _GoalsScreenState extends State<GoalsScreen> {
  final _repository = AdvisorRepository();
  late final Future<GoalSnapshot> _future = _repository.getGoal();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<GoalSnapshot>(
      future: _future,
      builder: (context, snapshot) {
        final goal = snapshot.data;
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
              _Panel(child: Text(snapshot.error.toString()))
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
                    value: '${goal.appointmentsNeeded}',
                    label: 'Target Appointments',
                  ),
                  _StatCard(
                    value: '${goal.dealsNeeded}',
                    label: 'Closed Deals',
                  ),
                  const _StatCard(value: '40%', label: 'Conversion Rate'),
                  _StatCard(
                    value: '${goal.leadsNeeded}',
                    label: 'Leads Needed',
                  ),
                ],
              ),
              const SizedBox(height: 14),
              _MonthlyGoalPanel(monthlyGoal: goal.annualGoalCents ~/ 12),
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

class _MonthlyGoalPanel extends StatelessWidget {
  const _MonthlyGoalPanel({required this.monthlyGoal});

  final int monthlyGoal;

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
                child: Container(
                  height: 42,
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF7FBFD),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: const Color(0xFFCFE4EC)),
                  ),
                  child: Row(
                    children: [
                      const Text(
                        '\$',
                        style: TextStyle(
                          color: Color(0xFF58707D),
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          '${(monthlyGoal / 100).round()}',
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: Color(0xFF202860),
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              SizedBox(
                height: 42,
                width: compact ? 76 : 64,
                child: FilledButton(
                  onPressed: () {},
                  style: FilledButton.styleFrom(
                    minimumSize: Size.zero,
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                  child: const Text('Save'),
                ),
              ),
            ],
          );
        },
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
  const _Panel({
    required this.child,
    this.padding = const EdgeInsets.all(16),
  });

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
