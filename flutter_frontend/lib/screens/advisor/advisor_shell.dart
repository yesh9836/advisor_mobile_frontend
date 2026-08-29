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

class AdvisorShell extends StatefulWidget {
  const AdvisorShell({super.key});

  @override
  State<AdvisorShell> createState() => _AdvisorShellState();
}

class _AdvisorShellState extends State<AdvisorShell> {
  int _selectedIndex = 0;

  void _selectTab(int index) {
    setState(() => _selectedIndex = index);
  }

  @override
  Widget build(BuildContext context) {
    final screens = [
      AdvisorDashboardScreen(
        onBuyLeads: () => _selectTab(2),
        onViewInbox: () => _selectTab(3),
        onOpenProfile: () => _selectTab(4),
      ),
      GoalsScreen(onSeeAllPackages: () => _selectTab(2)),
      const SubscriptionScreen(),
      const LeadsScreen(),
      const ProfileScreen(),
    ];

    return Scaffold(
      body: SafeArea(child: screens[_selectedIndex]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: _selectTab,
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            selectedIcon: Icon(Icons.dashboard),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.track_changes_outlined),
            selectedIcon: Icon(Icons.track_changes),
            label: 'Goals',
          ),
          NavigationDestination(
            icon: Icon(Icons.shopping_bag_outlined),
            selectedIcon: Icon(Icons.shopping_bag),
            label: 'Buy',
          ),
          NavigationDestination(
            icon: Icon(Icons.inbox_outlined),
            selectedIcon: Icon(Icons.inbox),
            label: 'Inbox',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person),
            label: 'Profile',
          ),
        ],
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
    final results = await Future.wait([
      _authRepository.getCurrentUser(),
      _repository.getDashboardSummary(),
      _repository.getLeads(deliveryStatus: 'all'),
    ]);
    return _DashboardData(
      user: results[0] as UserProfile,
      summary: results[1] as LeadDashboardSummary,
      leads: results[2] as List<AdvisorLead>,
    );
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
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 24),
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
              const SizedBox(height: 18),
              Row(
                children: [
                  Expanded(
                    child: _MetricCard(
                      label: 'Leads Delivered',
                      value: '${data.summary.leadsDelivered7Days}',
                      caption: '7 days',
                      icon: Icons.trending_up,
                      iconBackground: const Color(0xFFDFF7FC),
                      iconColor: const Color(0xFF18A0B8),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _MetricCard(
                      label: 'Appointments',
                      value: '${data.summary.appointmentsSet7Days}',
                      caption: '7 days',
                      icon: Icons.auto_graph,
                      iconBackground: const Color(0xFFE8DCFF),
                      iconColor: const Color(0xFF7C3AED),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _MetricCard(
                      label: 'Cost / Appt',
                      value: _money(data.summary.costPerAppointment),
                      caption: 'avg',
                      icon: Icons.trending_down,
                      iconBackground: const Color(0xFFEAF5FF),
                      iconColor: const Color(0xFF202860),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              SizedBox(
                height: 50,
                child: FilledButton.icon(
                  onPressed: widget.onBuyLeads,
                  icon: const Icon(Icons.shopping_bag_outlined),
                  label: const Text('Buy More Leads'),
                  style: FilledButton.styleFrom(
                    backgroundColor: const Color(0xFF18A0B8),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                    textStyle: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              _SectionHeader(
                title: 'Recent Leads',
                actionLabel: 'View all →',
                onAction: widget.onViewInbox,
              ),
              const SizedBox(height: 10),
              if (data.leads.isEmpty)
                const _EmptyPanel(
                  message:
                      'No matching leads yet. Seed demo data or buy a package.',
                )
              else
                for (final lead in data.leads.take(3))
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: _LeadTile(lead: lead, onTap: () => _openLead(lead)),
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
              const Text(
                'Lead notifications',
                style: TextStyle(
                  color: Color(0xFF202860),
                  fontSize: 20,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 6),
              const Text(
                'Delivery alerts for your new leads.',
                style: TextStyle(color: Color(0xFF315166)),
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
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Good morning,',
                style: TextStyle(
                  color: Color(0xFF315166),
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                user.name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: Color(0xFF202860),
                  fontSize: 21,
                  fontWeight: FontWeight.w900,
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
        const SizedBox(width: 10),
        Semantics(
          button: true,
          label: 'Open profile',
          child: Tooltip(
            message: 'Open profile',
            child: Material(
              color: const Color(0xFF202860),
              shape: const CircleBorder(),
              child: InkWell(
                onTap: onOpenProfile,
                customBorder: const CircleBorder(),
                child: SizedBox.square(
                  dimension: 38,
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
        color: Colors.white,
        shape: const CircleBorder(),
        child: InkWell(
          onTap: onPressed,
          customBorder: const CircleBorder(),
          child: Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: const Color(0xFFCFE4EC)),
            ),
            child: Icon(icon, color: const Color(0xFF202860), size: 21),
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
            style: const TextStyle(
              color: Color(0xFF202860),
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
    return Container(
      constraints: const BoxConstraints(minHeight: 112),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFCFE4EC)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0D0C5263),
            blurRadius: 18,
            offset: Offset(0, 9),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 30,
              height: 30,
              decoration: BoxDecoration(
                color: iconBackground,
                shape: BoxShape.circle,
              ),
              child: Icon(icon, color: iconColor, size: 17),
            ),
            const SizedBox(height: 10),
            Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: Color(0xFF202860),
                fontSize: 20,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 5),
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: Color(0xFF202860),
                fontSize: 10,
                fontWeight: FontWeight.w900,
              ),
            ),
            Text(
              caption,
              style: const TextStyle(color: Color(0xFF58707D), fontSize: 10),
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
            style: const TextStyle(
              color: Color(0xFF202860),
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
      color: Colors.white,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: Colors.transparent,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: const Color(0xFFCFE4EC)),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                radius: 20,
                backgroundColor: status.avatarColor,
                child: Text(
                  _leadInitials(lead),
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              const SizedBox(width: 12),
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
                            style: const TextStyle(
                              color: Color(0xFF202860),
                              fontSize: 15,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          _relativeTime(lead.receivedAt),
                          style: const TextStyle(
                            color: Color(0xFF315166),
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 7),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: [
                        _MiniBadge(
                          label: lead.stateCode,
                          background: const Color(0xFFEAF5FF),
                          foreground: const Color(0xFF202860),
                        ),
                        _MiniBadge(
                          label: status.label,
                          background: status.background,
                          foreground: status.foreground,
                          dotColor: status.foreground,
                        ),
                      ],
                    ),
                    const SizedBox(height: 9),
                    Text(
                      lead.assets ?? 'Lead details pending',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Color(0xFF18A0B8),
                        fontSize: 13,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      lead.activity ?? 'Details available after delivery',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Color(0xFF315166),
                        fontSize: 12,
                        height: 1.25,
                      ),
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
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFCFE4EC)),
      ),
      child: Column(
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Delivery Settings',
                  style: TextStyle(
                    color: Color(0xFF202860),
                    fontSize: 16,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              TextButton(
                onPressed: () => onEdit(),
                style: TextButton.styleFrom(
                  foregroundColor: const Color(0xFF18A0B8),
                  backgroundColor: const Color(0xFFE8FBFF),
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
          const Divider(height: 20, color: Color(0xFFD7E7EE)),
          _SettingRow(
            icon: Icons.mail_outline,
            label: 'Email Alerts',
            enabled: summary.emailAlertsEnabled,
          ),
          const Divider(height: 20, color: Color(0xFFD7E7EE)),
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
            const Text(
              'Delivery Settings',
              style: TextStyle(
                color: Color(0xFF202860),
                fontSize: 21,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              'Choose how you want to be alerted when new leads are delivered.',
              style: TextStyle(color: Color(0xFF315166), height: 1.35),
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
            style: const TextStyle(
              color: Color(0xFF202860),
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
        child: Text(message, style: const TextStyle(color: Color(0xFF58707D))),
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
