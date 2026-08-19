class AdvisorLead {
  AdvisorLead({
    required this.id,
    required this.stateCode,
    this.zipCode,
    this.firstName,
    this.lastName,
    this.mobilePhone,
    this.preferredFollowUpMethod,
    this.bestTimeToReach,
    this.retirementTimeline,
    this.confidenceInLongTermPlan,
    this.assets,
    this.activity,
    this.planningToRelocateRetirement,
    this.expectedRetirementIncomeSource,
    this.annualHouseholdIncomeRange,
    this.retirementSavingsRange,
    this.monthlySavingsRange,
    this.investmentComfortLevel,
    this.mainPurposeForInvesting = const [],
    this.currentInvestmentStrategies = const [],
    this.hasFinancialAdvisor,
    this.ownsAnnuity,
    this.additionalNotes,
    this.outcomeStatus,
    this.outcomeNotes,
    this.outcomeUpdatedAt,
    this.receivedAt,
    this.isDownloaded = false,
    this.piiUnlocked = false,
  });

  final int id;
  final String stateCode;
  final String? zipCode;
  final String? firstName;
  final String? lastName;
  final String? mobilePhone;
  final String? preferredFollowUpMethod;
  final String? bestTimeToReach;
  final String? retirementTimeline;
  final String? confidenceInLongTermPlan;
  final String? assets;
  final String? activity;
  final String? planningToRelocateRetirement;
  final String? expectedRetirementIncomeSource;
  final String? annualHouseholdIncomeRange;
  final String? retirementSavingsRange;
  final String? monthlySavingsRange;
  final String? investmentComfortLevel;
  final List<String> mainPurposeForInvesting;
  final List<String> currentInvestmentStrategies;
  final String? hasFinancialAdvisor;
  final String? ownsAnnuity;
  final String? additionalNotes;
  final String? outcomeStatus;
  final String? outcomeNotes;
  final DateTime? outcomeUpdatedAt;
  final DateTime? receivedAt;
  final bool isDownloaded;
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
      zipCode: json['zip_code'] as String?,
      firstName: json['first_name'] as String?,
      lastName: json['last_name'] as String?,
      mobilePhone: json['mobile_phone'] as String?,
      preferredFollowUpMethod: json['preferred_follow_up_method'] as String?,
      bestTimeToReach: json['best_time_to_reach'] as String?,
      retirementTimeline: json['retirement_timeline'] as String?,
      confidenceInLongTermPlan: json['confidence_in_long_term_plan'] as String?,
      assets: json['total_investable_assets_range'] as String?,
      activity: json['most_important_retirement_activity'] as String?,
      planningToRelocateRetirement:
          json['planning_to_relocate_retirement'] as String?,
      expectedRetirementIncomeSource:
          json['expected_retirement_income_source'] as String?,
      annualHouseholdIncomeRange:
          json['annual_household_income_range'] as String?,
      retirementSavingsRange: json['retirement_savings_range'] as String?,
      monthlySavingsRange: json['monthly_savings_range'] as String?,
      investmentComfortLevel: json['investment_comfort_level'] as String?,
      mainPurposeForInvesting:
          (json['main_purpose_for_investing'] as List? ?? [])
              .map((item) => item.toString())
              .toList(),
      currentInvestmentStrategies:
          (json['current_investment_strategies'] as List? ?? [])
              .map((item) => item.toString())
              .toList(),
      hasFinancialAdvisor: json['has_financial_advisor'] as String?,
      ownsAnnuity: json['owns_annuity'] as String?,
      additionalNotes: json['additional_notes'] as String?,
      outcomeStatus: json['outcome_status'] as String?,
      outcomeNotes: json['outcome_notes'] as String?,
      outcomeUpdatedAt: _parseDateTime(json['outcome_updated_at'] as String?),
      receivedAt: _parseDateTime(json['received_at'] as String?),
      isDownloaded: json['is_downloaded'] as bool? ?? false,
      piiUnlocked: json['pii_unlocked'] as bool? ?? false,
    );
  }

  AdvisorLead copyWithOutcome({
    required String status,
    required String? notes,
    DateTime? updatedAt,
  }) {
    return AdvisorLead(
      id: id,
      stateCode: stateCode,
      zipCode: zipCode,
      firstName: firstName,
      lastName: lastName,
      mobilePhone: mobilePhone,
      preferredFollowUpMethod: preferredFollowUpMethod,
      bestTimeToReach: bestTimeToReach,
      retirementTimeline: retirementTimeline,
      confidenceInLongTermPlan: confidenceInLongTermPlan,
      assets: assets,
      activity: activity,
      planningToRelocateRetirement: planningToRelocateRetirement,
      expectedRetirementIncomeSource: expectedRetirementIncomeSource,
      annualHouseholdIncomeRange: annualHouseholdIncomeRange,
      retirementSavingsRange: retirementSavingsRange,
      monthlySavingsRange: monthlySavingsRange,
      investmentComfortLevel: investmentComfortLevel,
      mainPurposeForInvesting: mainPurposeForInvesting,
      currentInvestmentStrategies: currentInvestmentStrategies,
      hasFinancialAdvisor: hasFinancialAdvisor,
      ownsAnnuity: ownsAnnuity,
      additionalNotes: additionalNotes,
      outcomeStatus: status,
      outcomeNotes: notes,
      outcomeUpdatedAt: updatedAt ?? outcomeUpdatedAt,
      receivedAt: receivedAt,
      isDownloaded: isDownloaded,
      piiUnlocked: piiUnlocked,
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

class DeliverySettings {
  DeliverySettings({
    required this.emailAlertsEnabled,
    required this.smsAlertsEnabled,
    required this.version,
    required this.warnings,
  });

  final bool emailAlertsEnabled;
  final bool smsAlertsEnabled;
  final int version;
  final List<String> warnings;

  factory DeliverySettings.fromJson(Map<String, dynamic> json) {
    return DeliverySettings(
      emailAlertsEnabled: json['email_alerts_enabled'] as bool? ?? false,
      smsAlertsEnabled: json['sms_alerts_enabled'] as bool? ?? false,
      version: json['version'] as int? ?? 1,
      warnings: (json['warnings'] as List? ?? [])
          .map((warning) => warning.toString())
          .toList(),
    );
  }
}

class BillingHistoryData {
  BillingHistoryData({
    required this.invoices,
    required this.providerStatus,
    this.paymentMethod,
    this.degradationReason,
  });

  final BillingPaymentMethod? paymentMethod;
  final List<BillingInvoice> invoices;
  final String providerStatus;
  final String? degradationReason;

  factory BillingHistoryData.fromSummary(Map<String, dynamic> json) {
    final paymentMethodJson = json['payment_method'] as Map<String, dynamic>?;
    final invoices =
        (json['invoices'] as List? ?? [])
            .map(
              (item) => BillingInvoice.fromJson(item as Map<String, dynamic>),
            )
            .toList()
          ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return BillingHistoryData(
      paymentMethod: paymentMethodJson == null
          ? null
          : BillingPaymentMethod.fromJson(paymentMethodJson),
      invoices: invoices,
      providerStatus: json['provider_status'] as String? ?? 'healthy',
      degradationReason: json['degradation_reason'] as String?,
    );
  }

  factory BillingHistoryData.fromPurchaseHistory(Map<String, dynamic> json) {
    final invoices =
        (json['items'] as List? ?? [])
            .map(
              (item) =>
                  BillingInvoice.fromPurchase(item as Map<String, dynamic>),
            )
            .toList()
          ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return BillingHistoryData(
      invoices: invoices,
      providerStatus: 'degraded',
      degradationReason: 'billing_summary_unavailable',
    );
  }
}

class BillingPaymentMethod {
  BillingPaymentMethod({
    required this.brand,
    required this.last4,
    required this.expMonth,
    required this.expYear,
    required this.isPlaceholder,
  });

  final String brand;
  final String last4;
  final int expMonth;
  final int expYear;
  final bool isPlaceholder;

  factory BillingPaymentMethod.fromJson(Map<String, dynamic> json) {
    return BillingPaymentMethod(
      brand: json['brand'] as String? ?? 'Card',
      last4: json['last4'] as String? ?? '',
      expMonth: json['exp_month'] as int? ?? 0,
      expYear: json['exp_year'] as int? ?? 0,
      isPlaceholder: json['is_placeholder'] as bool? ?? false,
    );
  }
}

class BillingInvoice {
  BillingInvoice({
    required this.id,
    required this.amountPaidCents,
    required this.currency,
    required this.status,
    required this.createdAt,
    this.packageName,
    this.invoiceUrl,
  });

  final String id;
  final int amountPaidCents;
  final String currency;
  final String status;
  final DateTime createdAt;
  final String? packageName;
  final String? invoiceUrl;

  factory BillingInvoice.fromJson(Map<String, dynamic> json) {
    return BillingInvoice(
      id: json['stripe_invoice_id'] as String? ?? '',
      amountPaidCents: json['amount_paid_cents'] as int? ?? 0,
      currency: json['currency'] as String? ?? 'USD',
      status: json['status'] as String? ?? 'unknown',
      createdAt:
          DateTime.tryParse(json['created_at'] as String? ?? '')?.toLocal() ??
          DateTime.fromMillisecondsSinceEpoch(0),
      packageName: json['package_name'] as String?,
      invoiceUrl:
          json['invoice_pdf'] as String? ??
          json['hosted_invoice_url'] as String?,
    );
  }

  factory BillingInvoice.fromPurchase(Map<String, dynamic> json) {
    return BillingInvoice(
      id:
          json['stripe_payment_intent_id'] as String? ??
          json['order_reference'] as String? ??
          'purchase-${json['id']}',
      amountPaidCents: json['amount_cents'] as int? ?? 0,
      currency: json['currency'] as String? ?? 'USD',
      status: json['status'] as String? ?? 'unknown',
      createdAt:
          DateTime.tryParse(json['purchased_at'] as String? ?? '')?.toLocal() ??
          DateTime.fromMillisecondsSinceEpoch(0),
      packageName: json['package_name'] as String?,
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

class PurchaseCheckoutSession {
  PurchaseCheckoutSession({required this.sessionId, required this.url});

  final String sessionId;
  final Uri url;

  factory PurchaseCheckoutSession.fromJson(Map<String, dynamic> json) {
    return PurchaseCheckoutSession(
      sessionId: json['session_id'] as String? ?? '',
      url: Uri.parse(json['url'] as String? ?? ''),
    );
  }
}

class LeadPurchaseStatus {
  LeadPurchaseStatus({
    required this.id,
    required this.status,
    required this.checkoutSessionId,
    required this.creditsTotal,
    required this.creditsRemaining,
    this.packageName,
  });

  final int id;
  final String status;
  final String checkoutSessionId;
  final int creditsTotal;
  final int creditsRemaining;
  final String? packageName;

  bool get isCompleted => status.toLowerCase() == 'completed';

  bool get isTerminalFailure =>
      const {'failed', 'canceled', 'refunded'}.contains(status.toLowerCase());

  factory LeadPurchaseStatus.fromJson(Map<String, dynamic> json) {
    return LeadPurchaseStatus(
      id: json['id'] as int,
      status: json['status'] as String? ?? 'pending',
      checkoutSessionId: json['stripe_checkout_session_id'] as String? ?? '',
      creditsTotal: json['credits_total'] as int? ?? 0,
      creditsRemaining: json['credits_remaining'] as int? ?? 0,
      packageName: json['package_name'] as String?,
    );
  }
}

class GoalSnapshot {
  GoalSnapshot({
    required this.targetYear,
    required this.earnedYtdCents,
    required this.annualGoalCents,
    required this.averageCommissionCents,
    required this.appointmentToDealRateBps,
    required this.leadToAppointmentRateBps,
    required this.incomeProgressPercent,
    required this.appointmentsNeeded,
    required this.dealsNeeded,
    required this.leadsNeeded,
    required this.appointmentsRemaining,
    required this.dealsRemaining,
    required this.leadsRemaining,
    required this.closedDealsYtd,
    required this.recommendedMonthlyLeads,
    required this.pacingStatus,
    required this.pacingMessage,
    required this.packages,
  });

  final int targetYear;
  final int earnedYtdCents;
  final int annualGoalCents;
  final int averageCommissionCents;
  final int appointmentToDealRateBps;
  final int leadToAppointmentRateBps;
  final int incomeProgressPercent;
  final int appointmentsNeeded;
  final int dealsNeeded;
  final int leadsNeeded;
  final int appointmentsRemaining;
  final int dealsRemaining;
  final int leadsRemaining;
  final int closedDealsYtd;
  final int recommendedMonthlyLeads;
  final String pacingStatus;
  final String pacingMessage;
  final List<LeadPackage> packages;

  factory GoalSnapshot.fromJson(Map<String, dynamic> json) {
    final goal = json['goal'] as Map<String, dynamic>? ?? {};
    final derived = json['derived'] as Map<String, dynamic>? ?? {};
    final pacing = derived['pacing'] as Map<String, dynamic>? ?? {};
    final packageRows = json['packages'] as List? ?? [];
    return GoalSnapshot(
      targetYear: goal['target_year'] as int? ?? DateTime.now().year,
      earnedYtdCents: goal['earned_ytd_cents'] as int? ?? 0,
      annualGoalCents: goal['annual_income_goal_cents'] as int? ?? 0,
      averageCommissionCents: goal['average_commission_cents'] as int? ?? 0,
      appointmentToDealRateBps:
          goal['appointment_to_deal_rate_bps'] as int? ?? 0,
      leadToAppointmentRateBps:
          goal['lead_to_appointment_rate_bps'] as int? ?? 0,
      incomeProgressPercent: derived['income_progress_percent'] as int? ?? 0,
      appointmentsNeeded: derived['appointments_needed'] as int? ?? 0,
      dealsNeeded: derived['deals_needed'] as int? ?? 0,
      leadsNeeded: derived['leads_needed'] as int? ?? 0,
      appointmentsRemaining: derived['appointments_remaining'] as int? ?? 0,
      dealsRemaining: derived['deals_remaining'] as int? ?? 0,
      leadsRemaining: derived['leads_remaining'] as int? ?? 0,
      closedDealsYtd: derived['closed_deals_ytd'] as int? ?? 0,
      recommendedMonthlyLeads:
          derived['recommended_monthly_leads'] as int? ?? 0,
      pacingStatus: pacing['status'] as String? ?? '',
      pacingMessage: pacing['message'] as String? ?? '',
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
