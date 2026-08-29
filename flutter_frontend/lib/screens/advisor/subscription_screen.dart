import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:url_launcher/url_launcher.dart';

typedef CheckoutUrlLauncher = Future<bool> Function(Uri url);

class SubscriptionScreen extends StatefulWidget {
  const SubscriptionScreen({
    super.key,
    this.repository,
    this.checkoutUrlLauncher,
  });

  final AdvisorRepository? repository;
  final CheckoutUrlLauncher? checkoutUrlLauncher;

  @override
  State<SubscriptionScreen> createState() => _SubscriptionScreenState();
}

class _SubscriptionScreenState extends State<SubscriptionScreen>
    with WidgetsBindingObserver {
  late final AdvisorRepository _repository =
      widget.repository ?? AdvisorRepository();
  late final Future<_BuyData> _future;
  int? _selectedPackageId;
  final Set<String> _selectedStates = {};
  bool _saving = false;
  bool _checkingPurchase = false;
  String? _error;
  String? _checkoutNotice;
  PurchaseCheckoutSession? _activeCheckout;
  Timer? _checkoutPollTimer;
  int _checkoutPollAttempt = 0;
  String? _checkoutRetryToken;

  static const _checkoutPollInterval = Duration(milliseconds: 1500);
  static const _maxCheckoutPollAttempts = 40;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _future = _load();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _checkoutPollTimer?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && _activeCheckout != null) {
      unawaited(_checkPurchaseStatus());
    }
  }

  Future<_BuyData> _load() async {
    final results = await Future.wait([
      _repository.getPackages(),
      _repository.getDashboardSummary(),
    ]);
    final data = _BuyData(
      packages: results[0] as List<LeadPackage>,
      summary: results[1] as LeadDashboardSummary,
    );
    _selectedStates.addAll(data.summary.targetStates);
    return data;
  }

  Future<void> _continueToCheckout(_BuyData data) async {
    if (_saving) return;
    final selectedPackage = data.packages
        .where((item) => item.id == _selectedPackageId)
        .firstOrNull;
    if (selectedPackage == null) {
      setState(() => _error = 'Select a lead package.');
      return;
    }
    if (_selectedStates.isEmpty) {
      setState(() => _error = 'Select at least one target state.');
      return;
    }
    if (selectedPackage.stateLimit != null &&
        _selectedStates.length > selectedPackage.stateLimit!) {
      setState(
        () => _error =
            '${selectedPackage.name} supports up to '
            '${selectedPackage.stateLimit} target states.',
      );
      return;
    }

    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      _checkoutRetryToken ??=
          'mobile:${selectedPackage.id}:'
          '${DateTime.now().microsecondsSinceEpoch}';
      final checkout = await _repository.createPurchaseCheckout(
        packageId: selectedPackage.id,
        targetStates: _selectedStates.toList()..sort(),
        retryToken: _checkoutRetryToken,
      );
      if (checkout.demoMode) {
        if (!mounted) return;
        setState(() {
          _activeCheckout = checkout;
          _checkoutNotice =
              'Demo checkout completed — no payment was charged. '
              'Confirming your lead credits now.';
          _checkoutPollAttempt = 0;
        });
        await _checkPurchaseStatus();
        return;
      }
      final launcher =
          widget.checkoutUrlLauncher ??
          (url) => launchUrl(url, mode: LaunchMode.externalApplication);
      if (!await launcher(checkout.url)) {
        throw StateError('Unable to open secure checkout.');
      }
      if (!mounted) return;
      setState(() {
        _activeCheckout = checkout;
        _checkoutNotice =
            'Checkout opened securely. Return here after payment to confirm '
            'your lead credits.';
        _checkoutPollAttempt = 0;
      });
      _schedulePurchaseStatusCheck();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _schedulePurchaseStatusCheck() {
    _checkoutPollTimer?.cancel();
    if (_activeCheckout == null ||
        _checkoutPollAttempt >= _maxCheckoutPollAttempts) {
      return;
    }
    _checkoutPollTimer = Timer(
      _checkoutPollInterval,
      () => unawaited(_checkPurchaseStatus()),
    );
  }

  Future<void> _checkPurchaseStatus() async {
    final checkout = _activeCheckout;
    if (checkout == null || _checkingPurchase) return;
    _checkoutPollTimer?.cancel();
    setState(() => _checkingPurchase = true);
    try {
      final purchase = await _repository.getPurchaseByCheckoutSession(
        checkout.sessionId,
      );
      if (!mounted) return;
      if (purchase == null || purchase.status.toLowerCase() == 'pending') {
        setState(() {
          _checkoutNotice =
              'Payment is still being confirmed. Lead credits will appear '
              'automatically after Stripe confirms the purchase.';
          _checkoutPollAttempt += 1;
        });
        _schedulePurchaseStatusCheck();
        return;
      }
      if (purchase.isCompleted) {
        _checkoutPollTimer?.cancel();
        setState(() {
          _activeCheckout = null;
          _checkoutRetryToken = null;
          _selectedPackageId = null;
          _checkoutNotice =
              'Purchase complete. ${purchase.creditsTotal} lead credits '
              'were added${purchase.packageName == null ? '' : ' for ${purchase.packageName}'}.';
        });
        return;
      }
      if (purchase.isTerminalFailure) {
        _checkoutPollTimer?.cancel();
        setState(() {
          _activeCheckout = null;
          _checkoutRetryToken = null;
          _checkoutNotice =
              'Checkout ${purchase.status.toLowerCase()}. No new lead credits '
              'were added.';
        });
      }
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _checkoutNotice =
            'We could not confirm the purchase yet. You can check again '
            'without being charged twice.';
        _checkoutPollAttempt += 1;
      });
      _schedulePurchaseStatusCheck();
    } finally {
      if (mounted) setState(() => _checkingPurchase = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_BuyData>(
      future: _future,
      builder: (context, snapshot) {
        return ListView(
          padding: const EdgeInsets.fromLTRB(16, 20, 16, 24),
          children: [
            const Text(
              'Buy Leads',
              style: TextStyle(
                color: Color(0xFF202860),
                fontSize: 22,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 4),
            const Text(
              'Select a package and target states',
              style: TextStyle(color: Color(0xFF58707D)),
            ),
            const SizedBox(height: 16),
            if (snapshot.connectionState == ConnectionState.waiting)
              const Center(child: CircularProgressIndicator())
            else if (snapshot.hasError)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(snapshot.error.toString()),
                ),
              )
            else ...[
              _TargetStates(
                states: snapshot.data!.summary.targetStates,
                selectedStates: _selectedStates,
                onToggle: (state) {
                  setState(() {
                    if (_selectedStates.contains(state)) {
                      _selectedStates.remove(state);
                    } else {
                      _selectedStates.add(state);
                    }
                  });
                },
              ),
              const SizedBox(height: 14),
              for (final package in snapshot.data!.packages)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _PackageCard(
                    package: package,
                    selected: _selectedPackageId == package.id,
                    onTap: () {
                      setState(() => _selectedPackageId = package.id);
                    },
                  ),
                ),
              if (_checkoutNotice != null) ...[
                Container(
                  margin: const EdgeInsets.only(bottom: 12),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: const Color(0xFFE9F8FC),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: const Color(0xFF9BDCE8)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _checkoutNotice!,
                        style: const TextStyle(color: Color(0xFF335366)),
                      ),
                      if (_activeCheckout != null) ...[
                        const SizedBox(height: 8),
                        TextButton.icon(
                          onPressed: _checkingPurchase
                              ? null
                              : _checkPurchaseStatus,
                          icon: _checkingPurchase
                              ? const SizedBox.square(
                                  dimension: 14,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Icon(Icons.refresh, size: 18),
                          label: const Text('Check purchase status'),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: 2),
                Text(_error!, style: const TextStyle(color: Color(0xFFB91C1C))),
                const SizedBox(height: 10),
              ],
              SizedBox(
                height: 50,
                child: FilledButton(
                  onPressed: _saving
                      ? null
                      : () => _continueToCheckout(snapshot.data!),
                  style: FilledButton.styleFrom(
                    backgroundColor: const Color(0xFF18A0B8),
                  ),
                  child: Text(
                    _saving ? 'Saving selection...' : 'Continue to checkout',
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

class _BuyData {
  _BuyData({required this.packages, required this.summary});

  final List<LeadPackage> packages;
  final LeadDashboardSummary summary;
}

class _TargetStates extends StatelessWidget {
  const _TargetStates({
    required this.states,
    required this.selectedStates,
    required this.onToggle,
  });

  final List<String> states;
  final Set<String> selectedStates;
  final ValueChanged<String> onToggle;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFCFE4EC)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0F0C5263),
            blurRadius: 20,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Target States',
              style: TextStyle(
                color: Color(0xFF202860),
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 12),
            if (states.isEmpty)
              const Text(
                'Add and verify a license before selecting target states.',
                style: TextStyle(color: Color(0xFF58707D)),
              )
            else
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final state in states)
                    _StateChip(
                      state: state,
                      selected: selectedStates.contains(state),
                      onTap: () => onToggle(state),
                    ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

class _StateChip extends StatelessWidget {
  const _StateChip({
    required this.state,
    required this.selected,
    required this.onTap,
  });

  final String state;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? const Color(0xFF202860) : const Color(0xFFF4FAFC),
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: onTap,
        child: Container(
          constraints: const BoxConstraints(minWidth: 54),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
              color: selected
                  ? const Color(0xFF202860)
                  : const Color(0xFFCFE4EC),
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (selected) ...[
                const Icon(Icons.check, color: Colors.white, size: 14),
                const SizedBox(width: 5),
              ],
              Text(
                state,
                style: TextStyle(
                  color: selected ? Colors.white : const Color(0xFF58707D),
                  fontSize: 12,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PackageCard extends StatelessWidget {
  const _PackageCard({
    required this.package,
    required this.selected,
    required this.onTap,
  });

  final LeadPackage package;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final badge = _packageBadge(package);

    return AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      decoration: BoxDecoration(
        color: selected ? const Color(0xFFF4FDFF) : Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: selected ? const Color(0xFF18A0B8) : const Color(0xFFD8E8EE),
          width: selected ? 1.6 : 1,
        ),
        boxShadow: [
          BoxShadow(
            color: selected ? const Color(0x3318A0B8) : const Color(0x0D0C5263),
            blurRadius: selected ? 24 : 14,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  selected ? Icons.check_circle : Icons.radio_button_unchecked,
                  color: selected
                      ? const Color(0xFF18A0B8)
                      : const Color(0xFFC7D7DD),
                ),
                const SizedBox(width: 12),
                Expanded(
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
                                fontSize: 18,
                                fontWeight: FontWeight.w900,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            '${package.creditsTotal} leads',
                            style: const TextStyle(color: Color(0xFF58707D)),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        package.stateLimit == null
                            ? 'All verified states'
                            : 'Up to ${package.stateLimit} target states',
                        style: const TextStyle(color: Color(0xFF58707D)),
                      ),
                      const SizedBox(height: 16),
                      Text(
                        _money(package.priceCents),
                        style: TextStyle(
                          color: selected
                              ? const Color(0xFF18A0B8)
                              : const Color(0xFF202860),
                          fontSize: 28,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      Row(
                        children: [
                          Text(
                            '${_money(package.costPerLeadCents)}/lead',
                            style: const TextStyle(color: Color(0xFF58707D)),
                          ),
                          if (badge != null) ...[
                            const Spacer(),
                            _PackageBadge(label: badge),
                          ],
                        ],
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

class _PackageBadge extends StatelessWidget {
  const _PackageBadge({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: const Color(0xFFE8FBFF),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: Color(0xFF18A0B8),
          fontSize: 10,
          fontWeight: FontWeight.w900,
        ),
      ),
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
