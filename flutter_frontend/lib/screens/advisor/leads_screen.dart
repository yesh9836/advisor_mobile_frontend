import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/screens/advisor/lead_details_sheet.dart';
import 'package:flutter_frontend/theme/app_components.dart';
import 'package:flutter_frontend/theme/app_theme.dart';

class LeadsScreen extends StatefulWidget {
  const LeadsScreen({super.key, this.repository});

  final AdvisorRepository? repository;

  @override
  State<LeadsScreen> createState() => _LeadsScreenState();
}

class _LeadsScreenState extends State<LeadsScreen> {
  late final AdvisorRepository _repository =
      widget.repository ?? AdvisorRepository();
  final _searchController = TextEditingController();
  Timer? _searchDebounce;
  String _selectedOutcome = 'all';
  String _selectedDelivery = 'all';
  late Future<List<AdvisorLead>> _future = _loadLeads();

  Future<List<AdvisorLead>> _loadLeads() {
    return _repository.getLeads(
      deliveryStatus: _selectedDelivery,
      outcomeStatus: _selectedOutcome,
      search: _searchController.text,
    );
  }

  void _refreshLeads() {
    setState(() {
      _future = _loadLeads();
    });
  }

  Future<void> _openLead(AdvisorLead lead) {
    return showLeadDetailsSheet(
      context: context,
      lead: lead,
      repository: _repository,
      onUpdated: (_) => _refreshLeads(),
    );
  }

  void _onSearchChanged(String _) {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 350), _refreshLeads);
  }

  Future<void> _openFilters() async {
    final selected = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) => _InboxFilterSheet(selected: _selectedDelivery),
    );
    if (!mounted || selected == null || selected == _selectedDelivery) return;
    setState(() {
      _selectedDelivery = selected;
      _future = _loadLeads();
    });
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<AdvisorLead>>(
      future: _future,
      builder: (context, snapshot) {
        final leads = snapshot.data ?? [];
        return ListView(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 112),
          children: [
            AppScreenHeader(
              eyebrow: 'Pipeline',
              title: 'Lead Inbox',
              subtitle: 'Prioritize conversations and move prospects forward.',
              icon: Icons.inbox_rounded,
              titleBadge: _CountBadge(count: leads.length),
            ),
            const SizedBox(height: 10),
            _SearchField(
              controller: _searchController,
              onChanged: _onSearchChanged,
              filterActive: _selectedDelivery != 'all',
              onFilter: _openFilters,
            ),
            const SizedBox(height: 9),
            _StatusFilters(
              selected: _selectedOutcome,
              onSelected: (value) {
                if (_selectedOutcome == value) return;
                setState(() {
                  _selectedOutcome = value;
                  _future = _loadLeads();
                });
              },
            ),
            const SizedBox(height: 11),
            if (snapshot.connectionState == ConnectionState.waiting)
              const Padding(
                padding: EdgeInsets.only(top: 40),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (snapshot.hasError)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(snapshot.error.toString()),
                      const SizedBox(height: 12),
                      OutlinedButton.icon(
                        onPressed: () => setState(() {
                          _future = _loadLeads();
                        }),
                        icon: const Icon(Icons.wifi_protected_setup_rounded),
                        label: Text(
                          snapshot.error.toString().toLowerCase().contains(
                                'timed out',
                              )
                              ? 'Reconnect'
                              : 'Reload',
                        ),
                      ),
                    ],
                  ),
                ),
              )
            else if (leads.isEmpty)
              const _EmptyInbox()
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
                    for (var index = 0; index < leads.length; index++) ...[
                      _LeadCard(
                        lead: leads[index],
                        onTap: () => _openLead(leads[index]),
                      ),
                      if (index < leads.length - 1)
                        Divider(height: 1, color: context.appOutline),
                    ],
                  ],
                ),
              ),
          ],
        );
      },
    );
  }
}

class _CountBadge extends StatelessWidget {
  const _CountBadge({required this.count});

  final int count;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
      decoration: const BoxDecoration(
        color: Color(0xFF18A0B8),
        shape: BoxShape.circle,
      ),
      alignment: Alignment.center,
      child: Text(
        '$count',
        style: const TextStyle(
          color: Colors.white,
          fontSize: 12,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _SearchField extends StatelessWidget {
  const _SearchField({
    required this.controller,
    required this.onChanged,
    required this.filterActive,
    required this.onFilter,
  });

  final TextEditingController controller;
  final ValueChanged<String> onChanged;
  final bool filterActive;
  final VoidCallback onFilter;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: SizedBox(
            height: 46,
            child: TextField(
              controller: controller,
              onChanged: onChanged,
              textInputAction: TextInputAction.search,
              decoration: InputDecoration(
                hintText: 'Search leads...',
                prefixIcon: const Icon(Icons.search, size: 22),
                contentPadding: const EdgeInsets.symmetric(horizontal: 16),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide(color: context.appOutline),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide(color: context.appOutline),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(width: 8),
        Material(
          color: filterActive
              ? const Color(0xFF078AA2).withValues(alpha: .12)
              : context.appSurface,
          borderRadius: BorderRadius.circular(12),
          child: InkWell(
            key: const ValueKey('inbox-filter-button'),
            onTap: onFilter,
            borderRadius: BorderRadius.circular(12),
            child: Container(
              height: 46,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: filterActive
                      ? const Color(0xFF18A0B8)
                      : context.appOutline,
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    filterActive
                        ? Icons.filter_alt_rounded
                        : Icons.filter_list_rounded,
                    color: filterActive
                        ? const Color(0xFF078AA2)
                        : context.appInk,
                    size: 19,
                  ),
                  const SizedBox(width: 5),
                  Text(
                    'Filter',
                    style: TextStyle(
                      color: filterActive
                          ? const Color(0xFF078AA2)
                          : context.appInk,
                      fontWeight: FontWeight.w800,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _InboxFilterSheet extends StatelessWidget {
  const _InboxFilterSheet({required this.selected});

  final String selected;

  static const _options = <(String, String, IconData)>[
    ('all', 'All leads', Icons.layers_outlined),
    ('available', 'Available', Icons.lock_open_rounded),
    ('delivered', 'Delivered', Icons.verified_user_outlined),
  ];

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(18, 10, 18, 22),
        decoration: BoxDecoration(
          color: context.appSurface,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(26)),
          boxShadow: context.appCardShadows,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 42,
                height: 4,
                decoration: BoxDecoration(
                  color: context.appOutline,
                  borderRadius: BorderRadius.circular(99),
                ),
              ),
            ),
            const SizedBox(height: 18),
            Text(
              'Filter leads',
              style: TextStyle(
                color: context.appInk,
                fontSize: 21,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'Choose which delivery group to display.',
              style: TextStyle(color: context.appMuted),
            ),
            const SizedBox(height: 16),
            for (final option in _options)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Material(
                  color: selected == option.$1
                      ? const Color(0xFF18A0B8).withValues(alpha: .11)
                      : context.appSoftFill,
                  borderRadius: BorderRadius.circular(14),
                  child: InkWell(
                    key: ValueKey('delivery-filter-${option.$1}'),
                    onTap: () => Navigator.of(context).pop(option.$1),
                    borderRadius: BorderRadius.circular(14),
                    child: Padding(
                      padding: const EdgeInsets.all(13),
                      child: Row(
                        children: [
                          Icon(
                            option.$3,
                            color: selected == option.$1
                                ? const Color(0xFF078AA2)
                                : context.appMuted,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              option.$2,
                              style: TextStyle(
                                color: context.appInk,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                          if (selected == option.$1)
                            const Icon(
                              Icons.check_circle_rounded,
                              color: Color(0xFF18A0B8),
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _StatusFilters extends StatelessWidget {
  const _StatusFilters({required this.selected, required this.onSelected});

  final String selected;
  final ValueChanged<String> onSelected;

  static const _filters = [
    _LeadFilter(value: 'all', label: 'All'),
    _LeadFilter(value: 'new', label: 'New'),
    _LeadFilter(value: 'contacted', label: 'Contacted'),
    _LeadFilter(value: 'appointment_set', label: 'Appointment Set'),
    _LeadFilter(value: 'closed_deal', label: 'Closed'),
  ];

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          for (final filter in _filters)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: _FilterPill(
                label: filter.label,
                selected: selected == filter.value,
                onTap: () => onSelected(filter.value),
              ),
            ),
        ],
      ),
    );
  }
}

class _LeadFilter {
  const _LeadFilter({required this.value, required this.label});

  final String value;
  final String label;
}

class _FilterPill extends StatelessWidget {
  const _FilterPill({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected
          ? (context.isDarkMode
                ? const Color(0xFF23566B)
                : const Color(0xFF202860))
          : context.appSurface,
      borderRadius: BorderRadius.circular(999),
      child: InkWell(
        borderRadius: BorderRadius.circular(999),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 7),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(999),
            border: Border.all(
              color: selected
                  ? (context.isDarkMode
                        ? const Color(0xFF4BC9DA)
                        : const Color(0xFF202860))
                  : context.appOutline,
            ),
          ),
          child: Text(
            label,
            style: TextStyle(
              color: selected ? Colors.white : context.appMuted,
              fontSize: 12,
              fontWeight: FontWeight.w900,
            ),
          ),
        ),
      ),
    );
  }
}

class _LeadCard extends StatelessWidget {
  const _LeadCard({required this.lead, required this.onTap});

  final AdvisorLead lead;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final status = _LeadStatus.fromValue(lead.outcomeStatus);
    final initials = _initials(lead);

    return Container(
      color: context.appSurface,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(13),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _InitialAvatar(initials: initials, color: status.avatarColor),
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
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 5),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        crossAxisAlignment: WrapCrossAlignment.center,
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
                      const SizedBox(height: 7),
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              lead.assets ?? 'Price pending',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                color: context.appInk,
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
                                fontSize: 13,
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
      ),
    );
  }
}

class _InitialAvatar extends StatelessWidget {
  const _InitialAvatar({required this.initials, required this.color});

  final String initials;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return CircleAvatar(
      radius: 19,
      backgroundColor: color,
      child: Text(
        initials,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 14,
          fontWeight: FontWeight.w900,
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

class _EmptyInbox extends StatelessWidget {
  const _EmptyInbox();

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Row(
          children: [
            const Icon(Icons.inbox_outlined, color: Color(0xFF18A0B8)),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                'No leads match this view yet.',
                style: TextStyle(color: context.appMuted),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

String _initials(AdvisorLead lead) {
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
