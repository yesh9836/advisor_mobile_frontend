class AdvisorLead {
  AdvisorLead({
    required this.id,
    required this.stateCode,
    this.firstName,
    this.lastName,
    this.mobilePhone,
    this.assets,
    this.activity,
    this.outcomeStatus,
    this.receivedAt,
    this.piiUnlocked = false,
  });

  final int id;
  final String stateCode;
  final String? firstName;
  final String? lastName;
  final String? mobilePhone;
  final String? assets;
  final String? activity;
  final String? outcomeStatus;
  final DateTime? receivedAt;
  final bool piiUnlocked;

  String get displayName {
    final name = [
      firstName,
      lastName,
    ].where((part) => part != null && part.trim().isNotEmpty).join(' ');
    return name.isEmpty ? 'Available Lead' : name;
  }

  factory AdvisorLead.fromJson(Map<String, dynamic> json) {
    return AdvisorLead(
      id: json['id'] as int,
      stateCode: (json['state_code'] as String? ?? 'NA').toUpperCase(),
      firstName: json['first_name'] as String?,
      lastName: json['last_name'] as String?,
      mobilePhone: json['mobile_phone'] as String?,
      assets: json['total_investable_assets_range'] as String?,
      activity: json['most_important_retirement_activity'] as String?,
      outcomeStatus: json['outcome_status'] as String?,
      receivedAt: _parseDateTime(json['received_at'] as String?),
      piiUnlocked: json['pii_unlocked'] as bool? ?? false,
    );
  }
}

DateTime? _parseDateTime(String? value) {
  if (value == null || value.trim().isEmpty) return null;
  return DateTime.tryParse(value)?.toLocal();
}

class LeadDashboardSummary {
  LeadDashboardSummary({
    required this.leadsDelivered7Days,
    required this.appointmentsSet7Days,
    required this.costPerAppointment,
    required this.currency,
    required this.targetStates,
    required this.emailAlertsEnabled,
    required this.smsAlertsEnabled,
  });

  final int leadsDelivered7Days;
  final int appointmentsSet7Days;
  final double costPerAppointment;
  final String currency;
  final List<String> targetStates;
  final bool emailAlertsEnabled;
  final bool smsAlertsEnabled;

  factory LeadDashboardSummary.fromJson(Map<String, dynamic> json) {
    final settings = json['settings'] as Map<String, dynamic>? ?? {};
    return LeadDashboardSummary(
      leadsDelivered7Days: json['leads_delivered_7_days'] as int? ?? 0,
      appointmentsSet7Days: json['appointments_set_7_days'] as int? ?? 0,
      costPerAppointment: (json['cost_per_appointment'] as num? ?? 0)
          .toDouble(),
      currency: json['currency'] as String? ?? 'USD',
      targetStates: (settings['target_states'] as List? ?? [])
          .map((item) => item.toString())
          .toList(),
      emailAlertsEnabled: settings['email_alerts_enabled'] as bool? ?? false,
      smsAlertsEnabled: settings['sms_alerts_enabled'] as bool? ?? false,
    );
  }
}

class LeadPackage {
  LeadPackage({
    required this.id,
    required this.name,
    required this.priceCents,
    required this.creditsTotal,
    required this.stateLimit,
  });

  final int id;
  final String name;
  final int priceCents;
  final int creditsTotal;
  final int? stateLimit;

  int get costPerLeadCents =>
      creditsTotal <= 0 ? 0 : priceCents ~/ creditsTotal;

  factory LeadPackage.fromJson(Map<String, dynamic> json) {
    return LeadPackage(
      id: json['id'] as int,
      name: json['name'] as String? ?? 'Package',
      priceCents: json['price_cents'] as int? ?? 0,
      creditsTotal: json['credits_total'] as int? ?? 0,
      stateLimit: json['state_limit'] as int?,
    );
  }
}

class GoalSnapshot {
  GoalSnapshot({
    required this.earnedYtdCents,
    required this.annualGoalCents,
    required this.incomeProgressPercent,
    required this.appointmentsNeeded,
    required this.dealsNeeded,
    required this.leadsNeeded,
    required this.packages,
  });

  final int earnedYtdCents;
  final int annualGoalCents;
  final int incomeProgressPercent;
  final int appointmentsNeeded;
  final int dealsNeeded;
  final int leadsNeeded;
  final List<LeadPackage> packages;

  factory GoalSnapshot.fromJson(Map<String, dynamic> json) {
    final goal = json['goal'] as Map<String, dynamic>? ?? {};
    final derived = json['derived'] as Map<String, dynamic>? ?? {};
    final packageRows = json['packages'] as List? ?? [];
    return GoalSnapshot(
      earnedYtdCents: goal['earned_ytd_cents'] as int? ?? 0,
      annualGoalCents: goal['annual_income_goal_cents'] as int? ?? 0,
      incomeProgressPercent: derived['income_progress_percent'] as int? ?? 0,
      appointmentsNeeded: derived['appointments_needed'] as int? ?? 0,
      dealsNeeded: derived['deals_needed'] as int? ?? 0,
      leadsNeeded: derived['leads_needed'] as int? ?? 0,
      packages: packageRows.map((item) {
        final row = item as Map<String, dynamic>;
        return LeadPackage(
          id: row['package_id'] as int,
          name: row['name'] as String? ?? 'Package',
          priceCents: row['price_cents'] as int? ?? 0,
          creditsTotal: row['credits_per_package'] as int? ?? 0,
          stateLimit: row['state_limit'] as int?,
        );
      }).toList(),
    );
  }
}
