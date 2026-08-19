import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/screens/advisor/lead_details_sheet.dart';

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
  late Future<List<AdvisorLead>> _future = _loadLeads();

  Future<List<AdvisorLead>> _loadLeads() {
    return _repository.getLeads(
      deliveryStatus: 'all',
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
          padding: const EdgeInsets.fromLTRB(16, 20, 16, 24),
          children: [
            Row(
              children: [
                const Expanded(
                  child: Text(
                    'Lead Inbox',
                    style: TextStyle(
                      color: Color(0xFF202860),
                      fontSize: 22,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
                _CountBadge(count: leads.length),
              ],
            ),
            const SizedBox(height: 14),
            _SearchField(
              controller: _searchController,
              onChanged: _onSearchChanged,
            ),
            const SizedBox(height: 12),
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
            const SizedBox(height: 16),
            if (snapshot.connectionState == ConnectionState.waiting)
              const Padding(
                padding: EdgeInsets.only(top: 40),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (snapshot.hasError)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(snapshot.error.toString()),
                ),
              )
            else if (leads.isEmpty)
              const _EmptyInbox()
            else
              for (final lead in leads)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _LeadCard(lead: lead, onTap: () => _openLead(lead)),
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
  const _SearchField({required this.controller, required this.onChanged});

  final TextEditingController controller;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 48,
      child: TextField(
        controller: controller,
        onChanged: onChanged,
        textInputAction: TextInputAction.search,
        decoration: InputDecoration(
          hintText: 'Search leads...',
          prefixIcon: const Icon(Icons.search, size: 22),
          contentPadding: const EdgeInsets.symmetric(horizontal: 16),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(16),
            borderSide: const BorderSide(color: Color(0xFFCFE4EC)),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(16),
            borderSide: const BorderSide(color: Color(0xFFCFE4EC)),
          ),
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
      color: selected ? const Color(0xFF202860) : Colors.white,
      borderRadius: BorderRadius.circular(999),
      child: InkWell(
        borderRadius: BorderRadius.circular(999),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(999),
            border: Border.all(
              color: selected
                  ? const Color(0xFF202860)
                  : const Color(0xFFCFE4EC),
            ),
          ),
          child: Text(
            label,
            style: TextStyle(
              color: selected ? Colors.white : const Color(0xFF315166),
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
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFCFE4EC)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0D0C5263),
            blurRadius: 18,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _InitialAvatar(initials: initials, color: status.avatarColor),
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
                              color: Color(0xFF58707D),
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 7),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        crossAxisAlignment: WrapCrossAlignment.center,
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
                      const SizedBox(height: 10),
                      Text(
                        lead.assets ?? 'Lead details pending',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Color(0xFF202860),
                          fontSize: 13,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(height: 5),
                      Text(
                        lead.activity ?? 'Details available after delivery',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Color(0xFF315166),
                          fontSize: 13,
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
      radius: 21,
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
          children: const [
            Icon(Icons.inbox_outlined, color: Color(0xFF18A0B8)),
            SizedBox(width: 12),
            Expanded(
              child: Text(
                'No leads match this view yet.',
                style: TextStyle(color: Color(0xFF58707D)),
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
