import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/models/auth_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/screens/advisor/billing_history_sheet.dart';
import 'package:flutter_frontend/screens/advisor/change_password_sheet.dart';
import 'package:flutter_frontend/screens/advisor/license_upload_sheet.dart';
import 'package:flutter_frontend/screens/advisor/notification_preferences_sheet.dart';
import 'package:flutter_frontend/screens/advisor/profile_screen.dart';

void main() {
  testWidgets('submits a selected license document', (tester) async {
    final repository = _FakeAuthRepository();
    AdvisorLicense? submittedLicense;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: LicenseUploadSheet(
            repository: repository,
            documentPicker: () async => LicenseDocument(
              name: 'license.pdf',
              bytes: Uint8List.fromList('%PDF-test'.codeUnits),
              contentType: 'application/pdf',
            ),
            onSubmitted: (license) => submittedLicense = license,
          ),
        ),
      ),
    );

    await tester.enterText(find.widgetWithText(TextField, 'State code'), 'tx');
    await tester.enterText(
      find.widgetWithText(TextField, 'License number'),
      'LIC-123',
    );
    await tester.enterText(
      find.widgetWithText(TextField, 'License type (optional)'),
      'Life & Annuity',
    );
    await tester.tap(find.text('Select PDF or image'));
    await tester.pumpAndSettle();
    expect(find.text('license.pdf'), findsOneWidget);

    await tester.tap(find.widgetWithText(FilledButton, 'Submit License'));
    await tester.pumpAndSettle();

    expect(repository.submittedState, 'TX');
    expect(repository.submittedNumber, 'LIC-123');
    expect(repository.submittedFilename, 'license.pdf');
    expect(submittedLicense?.verificationStatus, 'pending');
    expect(find.text('License submitted for review.'), findsOneWidget);
  });

  testWidgets('treats closing the document picker as cancellation', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: LicenseUploadSheet(
            repository: _FakeAuthRepository(),
            documentPicker: () async => throw PlatformException(
              code: 'user_cancelled',
              message: 'Picker cancelled',
            ),
            onSubmitted: (_) {},
          ),
        ),
      ),
    );

    await tester.tap(find.text('Select PDF or image'));
    await tester.pumpAndSettle();

    expect(find.textContaining('could not be opened'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('does not update a closed sheet after upload failure', (
    tester,
  ) async {
    final repository = _FakeAuthRepository();
    final pending = Completer<AdvisorLicense>();
    repository.submitCompleter = pending;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: LicenseUploadSheet(
            repository: repository,
            documentPicker: () async => LicenseDocument(
              name: 'license.pdf',
              bytes: Uint8List.fromList('%PDF-test'.codeUnits),
              contentType: 'application/pdf',
            ),
            onSubmitted: (_) {},
          ),
        ),
      ),
    );
    await tester.enterText(find.widgetWithText(TextField, 'State code'), 'TX');
    await tester.enterText(
      find.widgetWithText(TextField, 'License number'),
      'LIC-123',
    );
    await tester.tap(find.text('Select PDF or image'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Submit License'));
    await tester.pump();

    await tester.pumpWidget(const MaterialApp(home: SizedBox.shrink()));
    pending.completeError(AuthException('Upload failed.'));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
  });

  testWidgets('renders payment method and billing history', (tester) async {
    final repository = _FakeAdvisorRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: BillingHistorySheet(repository: repository)),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('VISA •••• 4242'), findsOneWidget);
    expect(find.text('Starter Leads'), findsOneWidget);
    expect(find.text(r'$125'), findsOneWidget);
    expect(find.textContaining('Aug 9, 2026'), findsOneWidget);
  });

  testWidgets('opens license upload from Profile', (tester) async {
    final authRepository = _FakeAuthRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ProfileScreen(
            authRepository: authRepository,
            advisorRepository: _FakeAdvisorRepository(),
            documentPicker: () async => null,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(TextButton, 'Add'));
    await tester.pumpAndSettle();

    expect(find.text('License upload coming soon.'), findsNothing);
    expect(find.text('Upload License'), findsOneWidget);
    expect(find.text('Submit License'), findsOneWidget);
  });

  testWidgets('changes password after validating confirmation', (tester) async {
    final repository = _FakeAuthRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: ChangePasswordSheet(repository: repository)),
      ),
    );

    await tester.enterText(
      find.widgetWithText(TextFormField, 'Current password'),
      'StrongPass123!',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'New password'),
      'NewPass123!',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Confirm new password'),
      'NewPass123!',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Change Password'));
    await tester.pumpAndSettle();

    expect(repository.currentPassword, 'StrongPass123!');
    expect(repository.newPassword, 'NewPass123!');
  });

  testWidgets('loads and saves notification preferences', (tester) async {
    final repository = _FakeAdvisorRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: NotificationPreferencesSheet(repository: repository),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Email alerts'));
    await tester.tap(find.text('SMS alerts'));
    await tester.tap(find.widgetWithText(FilledButton, 'Save preferences'));
    await tester.pumpAndSettle();

    expect(repository.savedEmailEnabled, isFalse);
    expect(repository.savedSmsEnabled, isTrue);
    expect(repository.savedExpectedVersion, 4);
  });
}

class _FakeAuthRepository extends AuthRepository {
  String? submittedState;
  String? submittedNumber;
  String? submittedFilename;
  String? currentPassword;
  String? newPassword;
  Completer<AdvisorLicense>? submitCompleter;

  @override
  Future<UserProfile> getCurrentUser() async => UserProfile(
    id: 1,
    email: 'advisor@example.com',
    name: 'Test Advisor',
    role: 'advisor',
  );

  @override
  Future<List<AdvisorLicense>> getMyLicenses() async => [];

  @override
  Future<AdvisorLicense> submitLicense({
    required String state,
    required String licenseNumber,
    String? licenseType,
    required String filename,
    required Uint8List documentBytes,
    required String contentType,
  }) async {
    final pending = submitCompleter;
    if (pending != null) return pending.future;
    submittedState = state;
    submittedNumber = licenseNumber;
    submittedFilename = filename;
    return AdvisorLicense(
      id: 10,
      state: state,
      licenseNumber: licenseNumber,
      verificationStatus: 'pending',
      licenseType: licenseType,
    );
  }

  @override
  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    this.currentPassword = currentPassword;
    this.newPassword = newPassword;
  }
}

class _FakeAdvisorRepository extends AdvisorRepository {
  bool? savedEmailEnabled;
  bool? savedSmsEnabled;
  int? savedExpectedVersion;

  @override
  Future<BillingHistoryData> getBillingHistory() async => BillingHistoryData(
    providerStatus: 'healthy',
    paymentMethod: BillingPaymentMethod(
      brand: 'visa',
      last4: '4242',
      expMonth: 8,
      expYear: 2029,
      isPlaceholder: false,
    ),
    invoices: [
      BillingInvoice(
        id: 'in_123',
        amountPaidCents: 12500,
        currency: 'USD',
        status: 'paid',
        createdAt: DateTime(2026, 8, 9),
        packageName: 'Starter Leads',
      ),
    ],
  );

  @override
  Future<DeliverySettings> getDeliverySettings() async => DeliverySettings(
    emailAlertsEnabled: true,
    smsAlertsEnabled: false,
    version: 4,
    warnings: const [],
  );

  @override
  Future<DeliverySettings> updateDeliverySettings({
    required bool emailAlertsEnabled,
    required bool smsAlertsEnabled,
    required int expectedVersion,
  }) async {
    savedEmailEnabled = emailAlertsEnabled;
    savedSmsEnabled = smsAlertsEnabled;
    savedExpectedVersion = expectedVersion;
    return DeliverySettings(
      emailAlertsEnabled: emailAlertsEnabled,
      smsAlertsEnabled: smsAlertsEnabled,
      version: expectedVersion + 1,
      warnings: const [],
    );
  }
}
