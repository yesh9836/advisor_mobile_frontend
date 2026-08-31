import 'package:flutter_frontend/models/auth_models.dart';

class AdvisorOnboarding {
  const AdvisorOnboarding({
    required this.complete,
    required this.consentAccepted,
    required this.annualIncomeGoalCents,
    required this.averageSaleCents,
    required this.commissionRateBps,
    required this.closingRateBps,
    required this.leadToAppointmentRateBps,
    required this.averageCommissionCents,
    required this.dealsNeeded,
    required this.appointmentsNeeded,
    required this.leadsNeeded,
    required this.licenseStatus,
    required this.licenses,
  });

  final bool complete;
  final bool consentAccepted;
  final int annualIncomeGoalCents;
  final int averageSaleCents;
  final int commissionRateBps;
  final int closingRateBps;
  final int leadToAppointmentRateBps;
  final int averageCommissionCents;
  final int dealsNeeded;
  final int appointmentsNeeded;
  final int leadsNeeded;
  final String licenseStatus;
  final List<AdvisorLicense> licenses;

  AdvisorLicense? get rejectedLicense {
    for (final license in licenses) {
      if (license.verificationStatus == 'rejected') return license;
    }
    return null;
  }

  factory AdvisorOnboarding.fromJson(Map<String, dynamic> json) {
    final inputs = json['inputs'] as Map<String, dynamic>? ?? const {};
    final rows = json['licenses'] as List? ?? const [];
    return AdvisorOnboarding(
      complete: json['complete'] as bool? ?? false,
      consentAccepted: json['consent_accepted'] as bool? ?? false,
      annualIncomeGoalCents:
          inputs['annual_income_goal_cents'] as int? ?? 25000000,
      averageSaleCents: inputs['average_sale_cents'] as int? ?? 2500000,
      commissionRateBps: inputs['commission_rate_bps'] as int? ?? 2000,
      closingRateBps: inputs['closing_rate_bps'] as int? ?? 3300,
      leadToAppointmentRateBps:
          inputs['lead_to_appointment_rate_bps'] as int? ?? 3333,
      averageCommissionCents:
          json['average_commission_cents'] as int? ?? 500000,
      dealsNeeded: json['deals_needed'] as int? ?? 50,
      appointmentsNeeded: json['appointments_needed'] as int? ?? 152,
      leadsNeeded: json['leads_needed'] as int? ?? 457,
      licenseStatus: json['license_status'] as String? ?? 'not_submitted',
      licenses: rows
          .map((item) => AdvisorLicense.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }
}
