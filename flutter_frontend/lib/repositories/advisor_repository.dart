import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/models/onboarding_models.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/services/api_service.dart';

class AdvisorRepository {
  AdvisorRepository({ApiService? apiService})
    : _apiService = apiService ?? ApiService();

  final ApiService _apiService;

  Future<AdvisorOnboarding> getOnboarding() async {
    final response = await _apiService.get('/onboarding/me');
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(
        response.body,
        'Unable to load onboarding.',
      );
    }
    return AdvisorOnboarding.fromJson(
      decodeResponseObject(response.body, 'Unable to load onboarding.'),
    );
  }

  Future<AdvisorOnboarding> saveOnboarding({
    required int annualIncomeGoalCents,
    required int averageSaleCents,
    required int commissionRateBps,
    required int closingRateBps,
    required bool consentAccepted,
  }) async {
    final response = await _apiService.put(
      '/onboarding/me',
      body: {
        'annual_income_goal_cents': annualIncomeGoalCents,
        'average_sale_cents': averageSaleCents,
        'commission_rate_bps': commissionRateBps,
        'closing_rate_bps': closingRateBps,
        'consent_accepted': consentAccepted,
      },
    );
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(
        response.body,
        'Unable to save onboarding.',
      );
    }
    return AdvisorOnboarding.fromJson(
      decodeResponseObject(response.body, 'Unable to save onboarding.'),
    );
  }

  Future<LeadDashboardSummary> getDashboardSummary() async {
    final response = await _apiService.get('/leads/dashboard/summary');
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(
        response.body,
        'Unable to load dashboard.',
      );
    }
    return LeadDashboardSummary.fromJson(
      decodeResponseObject(response.body, 'Unable to load dashboard.'),
    );
  }

  Future<List<AdvisorLead>> getLeads({
    String deliveryStatus = 'all',
    String outcomeStatus = 'all',
    String? search,
  }) async {
    final query = Uri(
      queryParameters: {
        'page': '1',
        'size': '20',
        'delivery_status': deliveryStatus,
        'outcome_status': outcomeStatus,
        if (search != null && search.trim().isNotEmpty) 'search': search.trim(),
      },
    ).query;
    final response = await _apiService.get('/leads/?$query');
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(response.body, 'Unable to load leads.');
    }
    final data = decodeResponseObject(response.body, 'Unable to load leads.');
    return (data['items'] as List? ?? [])
        .map(
          (item) => AdvisorLead.fromJson(
            requireResponseObject(item, 'Unable to load leads.'),
          ),
        )
        .toList();
  }

  Future<AdvisorLead> updateLeadOutcome({
    required AdvisorLead lead,
    required String status,
    String? notes,
  }) async {
    final response = await _apiService.put(
      '/leads/${lead.id}/outcome',
      body: {
        'status': status,
        'notes': notes?.trim().isEmpty ?? true ? null : notes!.trim(),
      },
    );
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(
        response.body,
        'Unable to save lead outcome.',
      );
    }
    final data = decodeResponseObject(
      response.body,
      'Unable to save lead outcome.',
    );
    return lead.copyWithOutcome(
      status: data['status'] as String? ?? status,
      notes: data['notes'] as String?,
      updatedAt: DateTime.tryParse(
        data['updated_at'] as String? ?? '',
      )?.toLocal(),
    );
  }

  Future<List<LeadPackage>> getPackages() async {
    final response = await _apiService.get('/purchases/packages');
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(
        response.body,
        'Unable to load packages.',
      );
    }
    final data = decodeResponseList(response.body, 'Unable to load packages.');
    return data
        .map(
          (item) => LeadPackage.fromJson(
            requireResponseObject(item, 'Unable to load packages.'),
          ),
        )
        .toList();
  }

  Future<PurchaseCheckoutSession> createPurchaseCheckout({
    required int packageId,
    required List<String> targetStates,
    String? retryToken,
  }) async {
    final response = await _apiService.post(
      '/purchases/checkout',
      body: {
        'package_id': packageId,
        'target_states': targetStates,
        if (retryToken != null && retryToken.trim().isNotEmpty)
          'retry_token': retryToken.trim(),
      },
    );
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(
        response.body,
        'Unable to save package selection.',
      );
    }
    return PurchaseCheckoutSession.fromJson(
      decodeResponseObject(response.body, 'Unable to save package selection.'),
    );
  }

  Future<LeadPurchaseStatus?> getPurchaseByCheckoutSession(
    String checkoutSessionId,
  ) async {
    final response = await _apiService.get('/purchases/history?limit=50');
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(
        response.body,
        'Unable to confirm purchase status.',
      );
    }
    final data = decodeResponseObject(
      response.body,
      'Unable to confirm purchase status.',
    );
    for (final item in data['items'] as List? ?? const []) {
      final row = requireResponseObject(
        item,
        'Unable to confirm purchase status.',
      );
      if (row['stripe_checkout_session_id'] == checkoutSessionId) {
        return LeadPurchaseStatus.fromJson(row);
      }
    }
    return null;
  }

  Future<BillingHistoryData> getBillingHistory() async {
    final summaryResponse = await _apiService.get('/purchases/billing/summary');
    if (summaryResponse.statusCode == 200) {
      return BillingHistoryData.fromSummary(
        decodeResponseObject(
          summaryResponse.body,
          'Unable to load billing history.',
        ),
      );
    }

    final historyResponse = await _apiService.get(
      '/purchases/history?limit=50',
    );
    if (historyResponse.statusCode != 200) {
      throw AuthException.fromResponse(
        historyResponse.body,
        'Unable to load billing history.',
      );
    }
    return BillingHistoryData.fromPurchaseHistory(
      decodeResponseObject(
        historyResponse.body,
        'Unable to load billing history.',
      ),
    );
  }

  Future<DeliverySettings> getDeliverySettings() async {
    final response = await _apiService.get('/delivery-settings/me');
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(
        response.body,
        'Unable to load delivery settings.',
      );
    }
    return DeliverySettings.fromJson(
      decodeResponseObject(response.body, 'Unable to load delivery settings.'),
    );
  }

  Future<DeliverySettings> updateDeliverySettings({
    required bool emailAlertsEnabled,
    required bool smsAlertsEnabled,
    required int expectedVersion,
  }) async {
    final response = await _apiService.patch(
      '/delivery-settings/me',
      body: {
        'email_alerts_enabled': emailAlertsEnabled,
        'sms_alerts_enabled': smsAlertsEnabled,
        'expected_version': expectedVersion,
      },
    );
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(
        response.body,
        'Unable to update delivery settings.',
      );
    }
    return DeliverySettings.fromJson(
      decodeResponseObject(
        response.body,
        'Unable to update delivery settings.',
      ),
    );
  }

  Future<GoalSnapshot> getGoal() async {
    final response = await _apiService.get('/goals/me');
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(response.body, 'Unable to load goals.');
    }
    return GoalSnapshot.fromJson(
      decodeResponseObject(response.body, 'Unable to load goals.'),
    );
  }

  Future<GoalSnapshot> saveMonthlyGoal({
    required GoalSnapshot currentGoal,
    required int monthlyGoalCents,
  }) async {
    final response = await _apiService.put(
      '/goals/me',
      body: {
        'target_year': currentGoal.targetYear,
        'annual_income_goal_cents': monthlyGoalCents * 12,
        'average_commission_cents': currentGoal.averageCommissionCents,
        'earned_ytd_cents': currentGoal.earnedYtdCents,
        'appointment_to_deal_rate_bps': currentGoal.appointmentToDealRateBps,
        'lead_to_appointment_rate_bps': currentGoal.leadToAppointmentRateBps,
      },
    );
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(response.body, 'Unable to save goal.');
    }
    return GoalSnapshot.fromJson(
      decodeResponseObject(response.body, 'Unable to save goal.'),
    );
  }
}
