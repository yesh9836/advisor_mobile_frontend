import 'package:flutter/material.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/models/auth_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/screens/advisor/goals_screen.dart';
import 'package:flutter_frontend/screens/advisor/lead_details_sheet.dart';
import 'package:flutter_frontend/screens/advisor/leads_screen.dart';
import 'package:flutter_frontend/screens/advisor/profile_screen.dart';
import 'package:flutter_frontend/screens/advisor/subscription_screen.dart';
import 'package:flutter_frontend/theme/app_components.dart';
import 'package:flutter_frontend/theme/app_theme.dart';
import 'package:flutter_frontend/theme/app_theme_controller.dart';

class AdvisorShell extends StatefulWidget {
  const AdvisorShell({super.key, this.initialIndex = 0});

  final int initialIndex;

  @override
  State<AdvisorShell> createState() => _AdvisorShellState();
}

class _AdvisorShellState extends State<AdvisorShell> {
  late int _selectedIndex = widget.initialIndex.clamp(0, 4);
  late final ValueNotifier<double> _navigationPosition = ValueNotifier(
    _selectedIndex.toDouble(),
  );
  late final List<Widget?> _screens;
  late final PageController _pageController = PageController(
    initialPage: _selectedIndex,
  );
  final ValueNotifier<int> _outcomeRevision = ValueNotifier<int>(0);

  @override
  void initState() {
    super.initState();
    _screens = List<Widget?>.filled(5, null);
    _screens[_selectedIndex] = _createScreen(_selectedIndex);
    _pageController.addListener(_trackPageTransition);
  }

  void _trackPageTransition() {
    final page = _pageController.page;
    if (page == null || (page - _navigationPosition.value).abs() < .001) {
      return;
    }
    _navigationPosition.value = page;
  }

  Widget _createScreen(int index) => switch (index) {
    0 => AdvisorDashboardScreen(
      onBuyLeads: () => _openBuyPage(),
      onViewInbox: () => _selectTab(3),
      onLeadOutcomeUpdated: _notifyOutcomeUpdated,
    ),
    1 => GoalsScreen(
      onSeeAllPackages: _openBuyPage,
      outcomeRevision: _outcomeRevision,
    ),
    2 => const SubscriptionScreen(),
    3 => LeadsScreen(onLeadOutcomeUpdated: _notifyOutcomeUpdated),
    4 => const ProfileScreen(),
    _ => const SizedBox.shrink(),
  };

  void _selectTab(int index) {
    if (index == _selectedIndex) return;
    setState(() {
      _screens[index] ??= _createScreen(index);
      _selectedIndex = index;
    });
    _pageController.animateToPage(
      index,
      duration: const Duration(milliseconds: 320),
      curve: Curves.easeOutCubic,
    );
  }

  void _openBuyPage([int? packageId]) {
    if (packageId != null) {
      setState(() {
        _screens[2] = SubscriptionScreen(initialPackageId: packageId);
      });
    }
    _selectTab(2);
  }

  void _notifyOutcomeUpdated() {
    _outcomeRevision.value++;
  }

  @override
  void dispose() {
    _pageController.removeListener(_trackPageTransition);
    _pageController.dispose();
    _navigationPosition.dispose();
    _outcomeRevision.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: context.appCanvas,
      body: Stack(
        fit: StackFit.expand,
        children: [
          DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: context.isDarkMode
                    ? const [Color(0xFF090909), Color(0xFF000000)]
                    : const [Color(0xFFF9FBFD), AppColors.canvas],
              ),
            ),
            child: SafeArea(
              child: PageView.builder(
                controller: _pageController,
                itemCount: _screens.length,
                onPageChanged: (index) {
                  if (_selectedIndex == index) return;
                  setState(() {
                    _screens[index] ??= _createScreen(index);
                    _selectedIndex = index;
                  });
                },
                itemBuilder: (context, index) =>
                    _screens[index] ??= _createScreen(index),
              ),
            ),
          ),
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: IgnorePointer(
              child: SizedBox(
                height: 142 + MediaQuery.viewPaddingOf(context).bottom,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        context.appCanvas.withValues(alpha: 0),
                        context.appCanvas.withValues(alpha: .08),
                        context.appCanvas.withValues(alpha: .34),
                        context.appCanvas.withValues(alpha: .72),
                        context.appCanvas,
                      ],
                      stops: const [0, .22, .5, .76, 1],
                    ),
                  ),
                ),
              ),
            ),
          ),
          Positioned(
            left: 12,
            right: 12,
            bottom: 7,
            child: SafeArea(
              top: false,
              child: Container(
                padding: const EdgeInsets.all(4),
                decoration: BoxDecoration(
                  color: context.appSurface.withValues(alpha: .92),
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(
                    color: context.appOutline.withValues(alpha: .65),
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(
                        alpha: context.isDarkMode ? .34 : .12,
                      ),
                      blurRadius: 20,
                      offset: const Offset(0, 8),
                    ),
                  ],
                ),
                clipBehavior: Clip.antiAlias,
                child: ValueListenableBuilder<double>(
                  valueListenable: _navigationPosition,
                  builder: (context, position, _) => _AdvisorNavigationBar(
                    selectedIndex: _selectedIndex,
                    transitionPosition: position,
                    onDestinationSelected: _selectTab,
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

class _AdvisorNavigationBar extends StatelessWidget {
  const _AdvisorNavigationBar({
    required this.selectedIndex,
    required this.transitionPosition,
    required this.onDestinationSelected,
  });

  final int selectedIndex;
  final double transitionPosition;
  final ValueChanged<int> onDestinationSelected;

  static const _items = <_AdvisorNavigationItem>[
    _AdvisorNavigationItem(
      label: 'Home',
      icon: Icons.dashboard_outlined,
      selectedIcon: Icons.dashboard_rounded,
      color: Color(0xFF0F9F98),
    ),
    _AdvisorNavigationItem(
      label: 'Goals',
      icon: Icons.track_changes_outlined,
      selectedIcon: Icons.track_changes_rounded,
      color: Color(0xFF6366D9),
    ),
    _AdvisorNavigationItem(
      label: 'Buy',
      icon: Icons.shopping_bag_outlined,
      selectedIcon: Icons.shopping_bag_rounded,
      color: Color(0xFFD58416),
    ),
    _AdvisorNavigationItem(
      label: 'Inbox',
      icon: Icons.inbox_outlined,
      selectedIcon: Icons.inbox_rounded,
      color: Color(0xFF1687C8),
    ),
    _AdvisorNavigationItem(
      label: 'Profile',
      icon: Icons.person_outline_rounded,
      selectedIcon: Icons.person_rounded,
      color: Color(0xFF8B5CC7),
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 54,
      child: Row(
        children: [
          for (var index = 0; index < _items.length; index++)
            Expanded(
              child: _AdvisorNavigationButton(
                item: _items[index],
                selected: selectedIndex == index,
                selectionProgress: (1 - (transitionPosition - index).abs())
                    .clamp(0.0, 1.0),
                onTap: () => onDestinationSelected(index),
              ),
            ),
        ],
      ),
    );
  }
}

class _AdvisorNavigationItem {
  const _AdvisorNavigationItem({
    required this.label,
    required this.icon,
    required this.selectedIcon,
    required this.color,
  });

  final String label;
  final IconData icon;
  final IconData selectedIcon;
  final Color color;
}

class _AdvisorNavigationButton extends StatelessWidget {
  const _AdvisorNavigationButton({
    required this.item,
    required this.selected,
    required this.selectionProgress,
    required this.onTap,
  });

  final _AdvisorNavigationItem item;
  final bool selected;
  final double selectionProgress;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final accent = context.isDarkMode
        ? Color.lerp(item.color, Colors.white, 0.16)!
        : item.color;
    final idleColor = context.appMuted;
    final displayColor = Color.lerp(idleColor, accent, selectionProgress)!;

    return Semantics(
      button: true,
      selected: selected,
      label: '${item.label}, tab',
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 2),
        child: Material(
          color: Colors.transparent,
          borderRadius: BorderRadius.circular(13),
          child: InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(13),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 190),
              curve: Curves.easeOutCubic,
              decoration: BoxDecoration(
                color: accent.withValues(
                  alpha: (context.isDarkMode ? 0.19 : 0.1) * selectionProgress,
                ),
                borderRadius: BorderRadius.circular(13),
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  AnimatedScale(
                    duration: const Duration(milliseconds: 230),
                    curve: Curves.easeOutBack,
                    scale: 1 + (.09 * selectionProgress),
                    child: _NavigationGlyph(
                      item: item,
                      selectionProgress: selectionProgress,
                      accent: displayColor,
                      idleColor: displayColor,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    item.label,
                    maxLines: 1,
                    style: TextStyle(
                      color: displayColor,
                      fontSize: 9.5,
                      fontWeight: selectionProgress > .5
                          ? FontWeight.w900
                          : FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _NavigationGlyph extends StatelessWidget {
  const _NavigationGlyph({
    required this.item,
    required this.selectionProgress,
    required this.accent,
    required this.idleColor,
  });

  final _AdvisorNavigationItem item;
  final double selectionProgress;
  final Color accent;
  final Color idleColor;

  @override
  Widget build(BuildContext context) {
    final visuallySelected = selectionProgress > .5;
    if (item.label == 'Home') {
      const colors = [
        Color(0xFF16A6B6),
        Color(0xFF7964D9),
        Color(0xFFF19B32),
        Color(0xFF27A974),
      ];
      return SizedBox(
        width: 24,
        height: 23,
        child: Stack(
          children: [
            _HomeBlock(
              left: 1,
              top: 1,
              width: 8,
              height: 8,
              color: Color.lerp(idleColor, colors[0], selectionProgress)!,
            ),
            _HomeBlock(
              right: 1,
              top: 1,
              width: 10,
              height: 6,
              color: Color.lerp(idleColor, colors[1], selectionProgress)!,
            ),
            _HomeBlock(
              left: 1,
              bottom: 1,
              width: 6,
              height: 10,
              color: Color.lerp(idleColor, colors[2], selectionProgress)!,
            ),
            _HomeBlock(
              right: 1,
              bottom: 1,
              width: 12,
              height: 12,
              color: Color.lerp(idleColor, colors[3], selectionProgress)!,
            ),
          ],
        ),
      );
    }

    if (item.label == 'Goals') {
      return SizedBox.square(
        dimension: 23,
        child: Stack(
          alignment: Alignment.center,
          children: [
            Icon(Icons.track_changes_rounded, color: accent, size: 23),
            AnimatedContainer(
              duration: const Duration(milliseconds: 190),
              width: 6,
              height: 6,
              decoration: BoxDecoration(
                color: Color.lerp(
                  idleColor,
                  const Color(0xFFEF4444),
                  selectionProgress,
                ),
                shape: BoxShape.circle,
                boxShadow: visuallySelected
                    ? [
                        BoxShadow(
                          color: const Color(0xFFEF4444).withValues(alpha: .35),
                          blurRadius: 5,
                        ),
                      ]
                    : null,
              ),
            ),
          ],
        ),
      );
    }

    return Icon(
      visuallySelected ? item.selectedIcon : item.icon,
      color: accent,
      size: 21 + selectionProgress,
    );
  }
}

class _HomeBlock extends StatelessWidget {
  const _HomeBlock({
    this.left,
    this.top,
    this.right,
    this.bottom,
    required this.width,
    required this.height,
    required this.color,
  });

  final double? left;
  final double? top;
  final double? right;
  final double? bottom;
  final double width;
  final double height;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Positioned(
      left: left,
      top: top,
      right: right,
      bottom: bottom,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 190),
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(2.5),
        ),
      ),
    );
  }
}

class AdvisorDashboardScreen extends StatefulWidget {
  const AdvisorDashboardScreen({
    super.key,
    required this.onBuyLeads,
    required this.onViewInbox,
    this.repository,
    this.authRepository,
    this.onLeadOutcomeUpdated,
  });

  final VoidCallback onBuyLeads;
  final VoidCallback onViewInbox;
  final AdvisorRepository? repository;
  final AuthRepository? authRepository;
  final VoidCallback? onLeadOutcomeUpdated;

  @override
  State<AdvisorDashboardScreen> createState() => _AdvisorDashboardScreenState();
}

class _AdvisorDashboardScreenState extends State<AdvisorDashboardScreen> {
  late final _repository = widget.repository ?? AdvisorRepository();
  late final _authRepository = widget.authRepository ?? AuthRepository();
  late Future<_DashboardData> _future = _load();
  DeliverySettings? _deliverySettings;
  bool? _emailAlertsOverride;
  bool? _smsAlertsOverride;
  var _savingDeliverySettings = false;

  Future<_DashboardData> _load() async {
    // Keep these startup requests on the shared persistent connection. On a
    // high-latency or lossy route, opening three TLS connections in parallel
    // is noticeably slower and less reliable than reusing one warm socket.
    final user = await _authRepository.getCurrentUser();
    final summary = await _repository.getDashboardSummary();
    final leads = await _repository.getLeads(deliveryStatus: 'all');
    return _DashboardData(user: user, summary: summary, leads: leads);
  }

  Future<void> _refreshDashboard() async {
    final future = _load();
    setState(() {
      _future = future;
    });
    await future;
  }

  Future<void> _updateDeliverySettings({
    required LeadDashboardSummary summary,
    bool? emailAlertsEnabled,
    bool? smsAlertsEnabled,
  }) async {
    if (_savingDeliverySettings) return;
    final previousEmail =
        _emailAlertsOverride ??
        _deliverySettings?.emailAlertsEnabled ??
        summary.emailAlertsEnabled;
    final previousSms =
        _smsAlertsOverride ??
        _deliverySettings?.smsAlertsEnabled ??
        summary.smsAlertsEnabled;

    setState(() {
      _savingDeliverySettings = true;
      if (emailAlertsEnabled != null) {
        _emailAlertsOverride = emailAlertsEnabled;
      }
      if (smsAlertsEnabled != null) {
        _smsAlertsOverride = smsAlertsEnabled;
      }
    });

    try {
      final current =
          _deliverySettings ?? await _repository.getDeliverySettings();
      final updated = await _repository.updateDeliverySettings(
        emailAlertsEnabled: emailAlertsEnabled ?? current.emailAlertsEnabled,
        smsAlertsEnabled: smsAlertsEnabled ?? current.smsAlertsEnabled,
        expectedVersion: current.version,
      );
      if (!mounted) return;
      setState(() {
        _deliverySettings = updated;
        _emailAlertsOverride = updated.emailAlertsEnabled;
        _smsAlertsOverride = updated.smsAlertsEnabled;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Delivery settings updated.')),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _emailAlertsOverride = previousEmail;
        _smsAlertsOverride = previousSms;
      });
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(error.toString())));
    } finally {
      if (mounted) setState(() => _savingDeliverySettings = false);
    }
  }

  Future<void> _openLead(AdvisorLead lead) {
    return showLeadDetailsSheet(
      context: context,
      lead: lead,
      repository: _repository,
      onUpdated: (_) {
        widget.onLeadOutcomeUpdated?.call();
        setState(() {
          _future = _load();
        });
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_DashboardData>(
      future: _future,
      builder: (context, snapshot) {
        final data = snapshot.data;
        return AppRefreshIndicator(
          onRefresh: _refreshDashboard,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(14, 10, 14, 112),
            children: [
              if (snapshot.connectionState == ConnectionState.waiting &&
                  data == null)
                const Center(
                  child: AppLoadingIndicator(label: 'Loading dashboard'),
                )
              else if (snapshot.hasError)
                _EmptyPanel(
                  message: snapshot.error.toString(),
                  onRetry: _refreshDashboard,
                )
              else ...[
                _HomeHeader(user: data!.user),
                const SizedBox(height: 12),
                Container(
                  decoration: BoxDecoration(
                    color: context.appSurface,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: context.appOutline),
                    boxShadow: context.appCardShadows,
                  ),
                  child: IntrinsicHeight(
                    child: Row(
                      children: [
                        Expanded(
                          child: _MetricCard(
                            label: 'Leads Delivered',
                            value: '${data.summary.leadsDelivered7Days}',
                            caption: '7 days',
                            icon: Icons.trending_up,
                            iconBackground: const Color(0xFFE0F7FA),
                            iconColor: const Color(0xFF078AA2),
                          ),
                        ),
                        Expanded(
                          child: _MetricCard(
                            label: 'Appointments',
                            value: '${data.summary.appointmentsSet7Days}',
                            caption: '7 days',
                            icon: Icons.auto_awesome_rounded,
                            iconBackground: const Color(0xFFF0E9FF),
                            iconColor: const Color(0xFF7C4DCC),
                          ),
                        ),
                        Expanded(
                          child: _MetricCard(
                            label: 'Cost / Appt',
                            value: _money(data.summary.costPerAppointment),
                            caption: 'avg',
                            icon: Icons.attach_money_rounded,
                            iconBackground: const Color(0xFFE7F8EF),
                            iconColor: const Color(0xFF15805D),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                SizedBox(
                  height: 46,
                  child: FilledButton.icon(
                    onPressed: widget.onBuyLeads,
                    icon: const Icon(Icons.shopping_bag_outlined),
                    label: const Text('Buy More Leads'),
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(0xFF18A0B8),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(13),
                      ),
                      textStyle: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                _SectionHeader(
                  title: 'Recent Leads',
                  actionLabel: 'View all →',
                  onAction: widget.onViewInbox,
                ),
                const SizedBox(height: 6),
                if (data.leads.isEmpty)
                  const _EmptyPanel(
                    message:
                        'No matching leads yet. Seed demo data or buy a package.',
                  )
                else
                  Container(
                    decoration: BoxDecoration(
                      color: context.appSurface,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: context.appOutline),
                      boxShadow: context.appCardShadows,
                    ),
                    clipBehavior: Clip.antiAlias,
                    child: Column(
                      children: [
                        for (
                          var index = 0;
                          index < data.leads.length && index < 5;
                          index++
                        ) ...[
                          _LeadTile(
                            lead: data.leads[index],
                            onTap: () => _openLead(data.leads[index]),
                          ),
                          if (index < data.leads.length - 1 && index < 4)
                            Divider(height: 1, color: context.appOutline),
                        ],
                      ],
                    ),
                  ),
                const SizedBox(height: 2),
                _DeliverySettings(
                  emailAlertsEnabled:
                      _emailAlertsOverride ??
                      _deliverySettings?.emailAlertsEnabled ??
                      data.summary.emailAlertsEnabled,
                  smsAlertsEnabled:
                      _smsAlertsOverride ??
                      _deliverySettings?.smsAlertsEnabled ??
                      data.summary.smsAlertsEnabled,
                  saving: _savingDeliverySettings,
                  onEmailChanged: (value) => _updateDeliverySettings(
                    summary: data.summary,
                    emailAlertsEnabled: value,
                  ),
                  onSmsChanged: (value) => _updateDeliverySettings(
                    summary: data.summary,
                    smsAlertsEnabled: value,
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

class _DashboardData {
  _DashboardData({
    required this.user,
    required this.summary,
    required this.leads,
  });

  final UserProfile user;
  final LeadDashboardSummary summary;
  final List<AdvisorLead> leads;
}

class _HomeHeader extends StatelessWidget {
  const _HomeHeader({required this.user});

  final UserProfile user;

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
                children: [
                  Text(
                    'Welcome back,',
                    style: TextStyle(
                      color: context.appMuted,
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    user.name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: context.appInk,
                      fontSize: 22,
                      fontWeight: FontWeight.w900,
                      letterSpacing: -0.5,
                    ),
                  ),
                ],
              ),
            ),
            const AppThemeToggleButton(),
          ],
        ),
      ],
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.label,
    required this.value,
    required this.caption,
    required this.icon,
    required this.iconBackground,
    required this.iconColor,
  });

  final String label;
  final String value;
  final String caption;
  final IconData icon;
  final Color iconBackground;
  final Color iconColor;

  @override
  Widget build(BuildContext context) {
    final displayIconColor = context.isDarkMode
        ? Color.lerp(iconColor, Colors.white, 0.24)!
        : iconColor;

    return Container(
      constraints: const BoxConstraints(minHeight: 122),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 12, 8, 11),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: context.isDarkMode
                    ? displayIconColor.withValues(alpha: 0.24)
                    : iconBackground,
                shape: BoxShape.circle,
                border: context.isDarkMode
                    ? Border.all(
                        color: displayIconColor.withValues(alpha: 0.22),
                      )
                    : null,
              ),
              child: Icon(icon, color: displayIconColor, size: 19),
            ),
            const SizedBox(height: 7),
            Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: context.appInk,
                fontSize: 19,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 3),
            Text(
              label,
              maxLines: 2,
              overflow: TextOverflow.fade,
              style: TextStyle(
                color: context.appInk,
                fontSize: 11,
                fontWeight: FontWeight.w900,
                height: 1.15,
              ),
            ),
            Text(
              caption,
              style: TextStyle(color: context.appMuted, fontSize: 10),
            ),
          ],
        ),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({
    required this.title,
    required this.actionLabel,
    required this.onAction,
  });

  final String title;
  final String actionLabel;
  final VoidCallback onAction;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            title,
            style: TextStyle(
              color: context.appInk,
              fontSize: 16,
              fontWeight: FontWeight.w900,
            ),
          ),
        ),
        TextButton(
          onPressed: onAction,
          style: TextButton.styleFrom(
            foregroundColor: const Color(0xFF18A0B8),
            padding: EdgeInsets.zero,
            minimumSize: const Size(0, 32),
          ),
          child: Text(actionLabel),
        ),
      ],
    );
  }
}

class _LeadTile extends StatelessWidget {
  const _LeadTile({required this.lead, required this.onTap});

  final AdvisorLead lead;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final status = _LeadStatus.fromValue(lead.outcomeStatus);

    return Material(
      color: context.appSurface,
      child: InkWell(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          color: Colors.transparent,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              CircleAvatar(
                radius: 16,
                backgroundColor: status.avatarColor,
                child: Text(
                  _leadInitials(lead),
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              const SizedBox(width: 9),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(
                            lead.displayName,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: context.appInk,
                              fontSize: 13.5,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          _relativeTime(lead.receivedAt),
                          style: TextStyle(
                            color: context.appMuted,
                            fontSize: 11,
                          ),
                        ),
                        const SizedBox(width: 2),
                        Icon(
                          Icons.chevron_right_rounded,
                          size: 17,
                          color: context.appMuted,
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        _MiniBadge(
                          label: lead.stateCode,
                          background: context.appSoftFill,
                          foreground: context.appInk,
                        ),
                        _MiniBadge(
                          label: status.label,
                          background: status.background,
                          foreground: status.foreground,
                          dotColor: status.foreground,
                        ),
                        const SizedBox(width: 7),
                        Expanded(
                          child: Text(
                            '${lead.assets ?? 'Price pending'}  •  '
                            '${lead.activity ?? 'Category pending'}',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: Color(0xFF18A0B8),
                              fontSize: 11.5,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DeliverySettings extends StatelessWidget {
  const _DeliverySettings({
    required this.emailAlertsEnabled,
    required this.smsAlertsEnabled,
    required this.saving,
    required this.onEmailChanged,
    required this.onSmsChanged,
  });

  final bool emailAlertsEnabled;
  final bool smsAlertsEnabled;
  final bool saving;
  final ValueChanged<bool> onEmailChanged;
  final ValueChanged<bool> onSmsChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: context.appSurface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: context.appOutline),
        boxShadow: context.appCardShadows,
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Delivery Settings',
                  style: TextStyle(
                    color: context.appInk,
                    fontSize: 16,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              if (saving)
                const SizedBox.square(
                  dimension: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
            ],
          ),
          const Divider(height: 20),
          _SettingRow(
            icon: Icons.mail_outline,
            label: 'Email Alerts',
            enabled: emailAlertsEnabled,
            onChanged: saving ? null : onEmailChanged,
          ),
          const Divider(height: 20),
          _SettingRow(
            icon: Icons.sms_outlined,
            label: 'SMS Alerts',
            enabled: smsAlertsEnabled,
            onChanged: saving ? null : onSmsChanged,
          ),
        ],
      ),
    );
  }
}

class _DeliverySettingsEditor extends StatefulWidget {
  const _DeliverySettingsEditor({
    required this.initialSettings,
    required this.onSave,
  });

  final DeliverySettings initialSettings;
  final Future<DeliverySettings> Function(DeliverySettings settings) onSave;

  @override
  State<_DeliverySettingsEditor> createState() =>
      _DeliverySettingsEditorState();
}

class _DeliverySettingsEditorState extends State<_DeliverySettingsEditor> {
  late bool _emailEnabled = widget.initialSettings.emailAlertsEnabled;
  late bool _smsEnabled = widget.initialSettings.smsAlertsEnabled;
  late List<String> _warnings = widget.initialSettings.warnings;
  var _saving = false;
  String? _error;

  Future<void> _save() async {
    if (_saving) return;
    setState(() {
      _saving = true;
      _error = null;
    });

    try {
      final updated = await widget.onSave(
        DeliverySettings(
          emailAlertsEnabled: _emailEnabled,
          smsAlertsEnabled: _smsEnabled,
          version: widget.initialSettings.version,
          warnings: _warnings,
        ),
      );
      if (!mounted) return;
      setState(() => _warnings = updated.warnings);
      Navigator.of(context).pop();
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(
          20,
          4,
          20,
          24 + MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Delivery Settings',
              style: TextStyle(
                color: context.appInk,
                fontSize: 21,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'Choose how you want to be alerted when new leads are delivered.',
              style: TextStyle(color: context.appMuted, height: 1.35),
            ),
            const SizedBox(height: 18),
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              secondary: const Icon(
                Icons.mail_outline,
                color: Color(0xFF18A0B8),
              ),
              title: const Text('Email alerts'),
              subtitle: const Text('Receive lead delivery updates by email.'),
              value: _emailEnabled,
              onChanged: _saving
                  ? null
                  : (value) => setState(() => _emailEnabled = value),
            ),
            const Divider(),
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              secondary: const Icon(
                Icons.sms_outlined,
                color: Color(0xFF18A0B8),
              ),
              title: const Text('SMS alerts'),
              subtitle: const Text(
                'Receive lead delivery updates by text message.',
              ),
              value: _smsEnabled,
              onChanged: _saving
                  ? null
                  : (value) => setState(() => _smsEnabled = value),
            ),
            if (_warnings.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(
                _warnings.join('\n'),
                style: const TextStyle(color: Color(0xFFB45309), height: 1.35),
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: 10),
              Text(
                _error!,
                style: const TextStyle(color: Color(0xFFB91C1C), height: 1.35),
              ),
            ],
            const SizedBox(height: 18),
            SizedBox(
              width: double.infinity,
              height: 48,
              child: FilledButton(
                onPressed: _saving ? null : _save,
                style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFF18A0B8),
                ),
                child: Text(_saving ? 'Saving…' : 'Save preferences'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SettingRow extends StatelessWidget {
  const _SettingRow({
    required this.icon,
    required this.label,
    required this.enabled,
    required this.onChanged,
  });

  final IconData icon;
  final String label;
  final bool enabled;
  final ValueChanged<bool>? onChanged;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 32,
          height: 32,
          decoration: BoxDecoration(
            color: const Color(
              0xFF18A0B8,
            ).withValues(alpha: context.isDarkMode ? .15 : .09),
            shape: BoxShape.circle,
          ),
          child: Icon(icon, color: const Color(0xFF18A0B8), size: 18),
        ),
        const SizedBox(width: 11),
        Expanded(
          child: Text(
            label,
            style: TextStyle(
              color: context.appInk,
              fontWeight: FontWeight.w900,
            ),
          ),
        ),
        _CompactDeliveryToggle(
          label: '$label toggle',
          value: enabled,
          onChanged: onChanged,
        ),
      ],
    );
  }
}

class _CompactDeliveryToggle extends StatelessWidget {
  const _CompactDeliveryToggle({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  final String label;
  final bool value;
  final ValueChanged<bool>? onChanged;

  @override
  Widget build(BuildContext context) {
    final enabled = onChanged != null;
    return Semantics(
      button: true,
      toggled: value,
      label: label,
      excludeSemantics: true,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: enabled ? () => onChanged!(!value) : null,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 4),
          child: AnimatedOpacity(
            duration: const Duration(milliseconds: 160),
            opacity: enabled ? 1 : .55,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              curve: Curves.easeOutCubic,
              width: 50,
              height: 24,
              padding: const EdgeInsets.all(2),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: value
                      ? const [Color(0xFF76DD78), Color(0xFF28B75A)]
                      : const [Color(0xFFFF8A9A), Color(0xFFEF536B)],
                ),
                borderRadius: BorderRadius.circular(999),
                border: Border.all(
                  color: value
                      ? const Color(0xFF209D4C)
                      : const Color(0xFFD8455C),
                  width: .8,
                ),
                boxShadow: [
                  BoxShadow(
                    color:
                        (value
                                ? const Color(0xFF28B75A)
                                : const Color(0xFFEF536B))
                            .withValues(alpha: .2),
                    blurRadius: 7,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Stack(
                alignment: Alignment.center,
                children: [
                  AnimatedAlign(
                    duration: const Duration(milliseconds: 200),
                    curve: Curves.easeOutCubic,
                    alignment: value
                        ? Alignment.centerLeft
                        : Alignment.centerRight,
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 7),
                      child: Icon(
                        value ? Icons.check_rounded : Icons.close_rounded,
                        size: 15,
                        color: Colors.white,
                      ),
                    ),
                  ),
                  AnimatedAlign(
                    duration: const Duration(milliseconds: 200),
                    curve: Curves.easeOutCubic,
                    alignment: value
                        ? Alignment.centerRight
                        : Alignment.centerLeft,
                    child: Container(
                      width: 19,
                      height: 19,
                      decoration: BoxDecoration(
                        color: Colors.white,
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: .16),
                            blurRadius: 3,
                            offset: const Offset(0, 1),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _MiniBadge extends StatelessWidget {
  const _MiniBadge({
    required this.label,
    required this.background,
    required this.foreground,
    this.dotColor,
  });

  final String label;
  final Color background;
  final Color foreground;
  final Color? dotColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (dotColor != null) ...[
            Container(
              width: 6,
              height: 6,
              decoration: BoxDecoration(
                color: dotColor,
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: TextStyle(
              color: foreground,
              fontSize: 10,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    );
  }
}

class _LeadStatus {
  const _LeadStatus({
    required this.label,
    required this.background,
    required this.foreground,
    required this.avatarColor,
  });

  final String label;
  final Color background;
  final Color foreground;
  final Color avatarColor;

  static _LeadStatus fromValue(String? value) {
    switch (value) {
      case 'contacted':
        return const _LeadStatus(
          label: 'Contacted',
          background: Color(0xFFFFE9AD),
          foreground: Color(0xFFF59E0B),
          avatarColor: Color(0xFFF59E0B),
        );
      case 'appointment_set':
        return const _LeadStatus(
          label: 'Appointment Set',
          background: Color(0xFFE8DCFF),
          foreground: Color(0xFF7C3AED),
          avatarColor: Color(0xFF7C3AED),
        );
      case 'closed_deal':
        return const _LeadStatus(
          label: 'Closed',
          background: Color(0xFFDDFBEA),
          foreground: Color(0xFF059669),
          avatarColor: Color(0xFF059669),
        );
      default:
        return const _LeadStatus(
          label: 'New',
          background: Color(0xFFDFF7FC),
          foreground: Color(0xFF18A0B8),
          avatarColor: Color(0xFF18A0B8),
        );
    }
  }
}

class _EmptyPanel extends StatelessWidget {
  const _EmptyPanel({required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(message, style: TextStyle(color: context.appMuted)),
            if (onRetry != null) ...[
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.wifi_protected_setup_rounded),
                label: Text(
                  message.toLowerCase().contains('timed out')
                      ? 'Reconnect'
                      : 'Reload',
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

String _leadInitials(AdvisorLead lead) {
  final first = (lead.firstName ?? '').trim();
  final last = (lead.lastName ?? '').trim();
  if (first.isNotEmpty || last.isNotEmpty) {
    return [
      if (first.isNotEmpty) first.substring(0, 1),
      if (last.isNotEmpty) last.substring(0, 1),
    ].join().toUpperCase();
  }
  return lead.stateCode.length >= 2
      ? lead.stateCode.substring(0, 2).toUpperCase()
      : 'LD';
}

String _relativeTime(DateTime? dateTime) {
  if (dateTime == null) return 'Now';
  final difference = DateTime.now().difference(dateTime);
  if (difference.inMinutes < 1) return 'Now';
  if (difference.inHours < 1) return '${difference.inMinutes}m ago';
  if (difference.inDays < 1) return '${difference.inHours}h ago';
  if (difference.inDays < 7) return '${difference.inDays}d ago';
  final weeks = (difference.inDays / 7).floor();
  return '${weeks}w ago';
}

String _money(double value) => '\$${value.round()}';
