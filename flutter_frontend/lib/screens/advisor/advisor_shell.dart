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
  late final List<Widget?> _screens;

  @override
  void initState() {
    super.initState();
    _screens = List<Widget?>.filled(5, null);
    _screens[_selectedIndex] = _createScreen(_selectedIndex);
  }

  Widget _createScreen(int index) => switch (index) {
    0 => AdvisorDashboardScreen(
      onBuyLeads: () => _selectTab(2),
      onViewInbox: () => _selectTab(3),
      onOpenProfile: () => _selectTab(4),
    ),
    1 => GoalsScreen(onSeeAllPackages: () => _selectTab(2)),
    2 => const SubscriptionScreen(),
    3 => const LeadsScreen(),
    4 => const ProfileScreen(),
    _ => const SizedBox.shrink(),
  };

  void _selectTab(int index) {
    if (index == _selectedIndex) return;
    setState(() {
      _screens[index] ??= _createScreen(index);
      _selectedIndex = index;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: context.appCanvas,
      body: DecoratedBox(
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
          child: IndexedStack(
            index: _selectedIndex,
            children: [
              for (final screen in _screens) screen ?? const SizedBox.shrink(),
            ],
          ),
        ),
      ),
      bottomNavigationBar: Container(
        color: context.appCanvas,
        padding: const EdgeInsets.fromLTRB(12, 6, 12, 9),
        child: SafeArea(
          top: false,
          child: Container(
            padding: const EdgeInsets.all(5),
            decoration: BoxDecoration(
              color: context.appSurface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: context.appOutline),
              boxShadow: context.appCardShadows,
            ),
            clipBehavior: Clip.antiAlias,
            child: _AdvisorNavigationBar(
              selectedIndex: _selectedIndex,
              onDestinationSelected: _selectTab,
            ),
          ),
        ),
      ),
    );
  }
}

class _AdvisorNavigationBar extends StatelessWidget {
  const _AdvisorNavigationBar({
    required this.selectedIndex,
    required this.onDestinationSelected,
  });

  final int selectedIndex;
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
      height: 62,
      child: Row(
        children: [
          for (var index = 0; index < _items.length; index++)
            Expanded(
              child: _AdvisorNavigationButton(
                item: _items[index],
                selected: selectedIndex == index,
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
    required this.onTap,
  });

  final _AdvisorNavigationItem item;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final accent = context.isDarkMode
        ? Color.lerp(item.color, Colors.white, 0.16)!
        : item.color;
    final idleColor = context.appMuted;

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
                color: selected
                    ? accent.withValues(alpha: context.isDarkMode ? 0.19 : 0.1)
                    : Colors.transparent,
                borderRadius: BorderRadius.circular(13),
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    selected ? item.selectedIcon : item.icon,
                    color: selected ? accent : idleColor,
                    size: selected ? 22 : 21,
                  ),
                  const SizedBox(height: 3),
                  Text(
                    item.label,
                    maxLines: 1,
                    style: TextStyle(
                      color: selected ? accent : idleColor,
                      fontSize: 9.5,
                      fontWeight: selected ? FontWeight.w900 : FontWeight.w700,
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

class AdvisorDashboardScreen extends StatefulWidget {
  const AdvisorDashboardScreen({
    super.key,
    required this.onBuyLeads,
    required this.onViewInbox,
    required this.onOpenProfile,
  });

  final VoidCallback onBuyLeads;
  final VoidCallback onViewInbox;
  final VoidCallback onOpenProfile;

  @override
  State<AdvisorDashboardScreen> createState() => _AdvisorDashboardScreenState();
}

class _AdvisorDashboardScreenState extends State<AdvisorDashboardScreen> {
  final _repository = AdvisorRepository();
  final _authRepository = AuthRepository();
  late Future<_DashboardData> _future = _load();

  Future<_DashboardData> _load() async {
    // Keep these startup requests on the shared persistent connection. On a
    // high-latency or lossy route, opening three TLS connections in parallel
    // is noticeably slower and less reliable than reusing one warm socket.
    final user = await _authRepository.getCurrentUser();
    final summary = await _repository.getDashboardSummary();
    final leads = await _repository.getLeads(deliveryStatus: 'all');
    return _DashboardData(user: user, summary: summary, leads: leads);
  }

  Future<void> _openDeliverySettingsEditor() async {
    DeliverySettings settings;
    try {
      settings = await _repository.getDeliverySettings();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(error.toString())));
      return;
    }

    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _DeliverySettingsEditor(
        initialSettings: settings,
        onSave: (nextSettings) async {
          final updated = await _repository.updateDeliverySettings(
            emailAlertsEnabled: nextSettings.emailAlertsEnabled,
            smsAlertsEnabled: nextSettings.smsAlertsEnabled,
            expectedVersion: nextSettings.version,
          );
          if (!mounted) return updated;
          setState(() {
            _future = _load();
          });
          return updated;
        },
      ),
    );
  }

  Future<void> _openLead(AdvisorLead lead) {
    return showLeadDetailsSheet(
      context: context,
      lead: lead,
      repository: _repository,
      onUpdated: (_) {
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
        return ListView(
          padding: const EdgeInsets.fromLTRB(14, 10, 14, 18),
          children: [
            if (snapshot.connectionState == ConnectionState.waiting)
              const Center(child: CircularProgressIndicator())
            else if (snapshot.hasError)
              _EmptyPanel(message: snapshot.error.toString())
            else ...[
              _HomeHeader(
                user: data!.user,
                summary: data.summary,
                onOpenProfile: widget.onOpenProfile,
              ),
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
                        index < data.leads.length && index < 3;
                        index++
                      ) ...[
                        _LeadTile(
                          lead: data.leads[index],
                          onTap: () => _openLead(data.leads[index]),
                        ),
                        if (index < data.leads.length - 1 && index < 2)
                          Divider(height: 1, color: context.appOutline),
                      ],
                    ],
                  ),
                ),
              const SizedBox(height: 2),
              _DeliverySettings(
                summary: data.summary,
                onEdit: _openDeliverySettingsEditor,
              ),
            ],
          ],
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
  const _HomeHeader({
    required this.user,
    required this.summary,
    required this.onOpenProfile,
  });

  final UserProfile user;
  final LeadDashboardSummary summary;
  final VoidCallback onOpenProfile;

  void _showNotificationSheet(BuildContext context) {
    final hasNotificationsEnabled =
        summary.emailAlertsEnabled || summary.smsAlertsEnabled;
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Lead notifications',
                style: TextStyle(
                  color: context.appInk,
                  fontSize: 20,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'Delivery alerts for your new leads.',
                style: TextStyle(color: context.appMuted),
              ),
              const SizedBox(height: 18),
              _NotificationStatusRow(
                icon: Icons.mail_outline,
                label: 'Email alerts',
                enabled: summary.emailAlertsEnabled,
              ),
              const SizedBox(height: 12),
              _NotificationStatusRow(
                icon: Icons.sms_outlined,
                label: 'SMS alerts',
                enabled: summary.smsAlertsEnabled,
              ),
              if (!hasNotificationsEnabled) ...[
                const SizedBox(height: 16),
                const Text(
                  'Turn on an alert channel so new lead deliveries do not go unnoticed.',
                  style: TextStyle(color: Color(0xFFB45309), height: 1.35),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

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
                    'Good morning,',
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
            Stack(
              clipBehavior: Clip.none,
              children: [
                _CircleIconButton(
                  icon: Icons.notifications_none,
                  semanticLabel: 'Open notification settings',
                  onPressed: () => _showNotificationSheet(context),
                ),
                if (!summary.emailAlertsEnabled && !summary.smsAlertsEnabled)
                  Positioned(
                    right: 5,
                    top: 5,
                    child: Container(
                      width: 8,
                      height: 8,
                      decoration: const BoxDecoration(
                        color: Color(0xFFEF4444),
                        shape: BoxShape.circle,
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(width: 8),
            const AppThemeToggleButton(),
            const SizedBox(width: 9),
            Semantics(
              button: true,
              label: 'Open profile',
              child: Tooltip(
                message: 'Open profile',
                child: DecoratedBox(
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [Color(0xFF252D6D), Color(0xFF27B7CE)],
                    ),
                    shape: BoxShape.circle,
                  ),
                  child: Material(
                    color: Colors.transparent,
                    shape: const CircleBorder(),
                    child: InkWell(
                      onTap: onOpenProfile,
                      customBorder: const CircleBorder(),
                      child: SizedBox.square(
                        dimension: 40,
                        child: Center(
                          child: Text(
                            _initials(user.name),
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 13,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _CircleIconButton extends StatelessWidget {
  const _CircleIconButton({
    required this.icon,
    required this.semanticLabel,
    required this.onPressed,
  });

  final IconData icon;
  final String semanticLabel;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: semanticLabel,
      child: Material(
        color: context.appSurface,
        shape: const CircleBorder(),
        child: InkWell(
          onTap: onPressed,
          customBorder: const CircleBorder(),
          child: Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: context.appOutline),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x120C5263),
                  blurRadius: 10,
                  offset: Offset(0, 4),
                ),
              ],
            ),
            child: Icon(icon, color: context.appInk, size: 20),
          ),
        ),
      ),
    );
  }
}

class _NotificationStatusRow extends StatelessWidget {
  const _NotificationStatusRow({
    required this.icon,
    required this.label,
    required this.enabled,
  });

  final IconData icon;
  final String label;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    final color = enabled ? const Color(0xFF16A34A) : const Color(0xFF607987);
    return Row(
      children: [
        Icon(icon, color: const Color(0xFF18A0B8)),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            label,
            style: TextStyle(
              color: context.appInk,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        Text(
          enabled ? 'On' : 'Off',
          style: TextStyle(color: color, fontWeight: FontWeight.w900),
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
          padding: const EdgeInsets.all(12),
          color: Colors.transparent,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                radius: 18,
                backgroundColor: status.avatarColor,
                child: Text(
                  _leadInitials(lead),
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              const SizedBox(width: 10),
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
                              fontSize: 15,
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
                      ],
                    ),
                    const SizedBox(height: 5),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
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
                      ],
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Flexible(
                          child: Text(
                            lead.assets ?? 'Price pending',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: Color(0xFF18A0B8),
                              fontSize: 13,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text('•', style: TextStyle(color: context.appMuted)),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            lead.activity ?? 'Category pending',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: context.appMuted,
                              fontSize: 12,
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
  const _DeliverySettings({required this.summary, required this.onEdit});

  final LeadDashboardSummary summary;
  final Future<void> Function() onEdit;

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
              TextButton(
                onPressed: () => onEdit(),
                style: TextButton.styleFrom(
                  foregroundColor: const Color(0xFF18A0B8),
                  backgroundColor: context.appSoftFill,
                  minimumSize: const Size(0, 30),
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
                child: const Text('Edit'),
              ),
            ],
          ),
          const Divider(height: 20),
          _SettingRow(
            icon: Icons.mail_outline,
            label: 'Email Alerts',
            enabled: summary.emailAlertsEnabled,
          ),
          const Divider(height: 20),
          _SettingRow(
            icon: Icons.notifications_none,
            label: 'SMS Alerts',
            enabled: summary.smsAlertsEnabled,
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
  });

  final IconData icon;
  final String label;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    final color = enabled ? const Color(0xFF16A34A) : const Color(0xFF607987);
    return Row(
      children: [
        Icon(icon, color: const Color(0xFF18A0B8), size: 19),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            label,
            style: TextStyle(
              color: context.appInk,
              fontWeight: FontWeight.w900,
            ),
          ),
        ),
        Text(
          enabled ? 'ON' : 'OFF',
          style: TextStyle(
            color: color,
            fontSize: 12,
            fontWeight: FontWeight.w900,
          ),
        ),
        const SizedBox(width: 8),
        Container(
          width: 6,
          height: 6,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
      ],
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
  const _EmptyPanel({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Text(message, style: TextStyle(color: context.appMuted)),
      ),
    );
  }
}

String _initials(String name) {
  final parts = name
      .trim()
      .split(RegExp(r'\s+'))
      .where((part) => part.isNotEmpty)
      .toList();
  if (parts.isEmpty) return 'AD';
  if (parts.length == 1) return parts.first.substring(0, 1).toUpperCase();
  return '${parts.first.substring(0, 1)}${parts.last.substring(0, 1)}'
      .toUpperCase();
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
