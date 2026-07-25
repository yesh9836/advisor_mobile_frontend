import 'dart:convert';

import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/services/api_service.dart';

class AdvisorRepository {
  AdvisorRepository({ApiService? apiService})
    : _apiService = apiService ?? ApiService();

  final ApiService _apiService;

  Future<LeadDashboardSummary> getDashboardSummary() async {
    final response = await _apiService.get('/leads/dashboard/summary');
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(
        response.body,
        'Unable to load dashboard.',
      );
    }
    return LeadDashboardSummary.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
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
        if (search != null && search.trim().isNotEmpty)
          'search': search.trim(),
      },
    ).query;
    final response = await _apiService.get('/leads/?$query');
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(response.body, 'Unable to load leads.');
    }
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return (data['items'] as List? ?? [])
        .map((item) => AdvisorLead.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<List<LeadPackage>> getPackages() async {
    final response = await _apiService.get('/purchases/packages');
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(
        response.body,
        'Unable to load packages.',
      );
    }
    final data = jsonDecode(response.body) as List;
    return data
        .map((item) => LeadPackage.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<GoalSnapshot> getGoal() async {
    final response = await _apiService.get('/goals/me');
    if (response.statusCode != 200) {
      throw AuthException.fromResponse(response.body, 'Unable to load goals.');
    }
    return GoalSnapshot.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }
}
