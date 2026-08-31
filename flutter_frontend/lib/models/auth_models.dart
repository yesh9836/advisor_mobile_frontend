class LoginRequest {
  LoginRequest({required this.email, required this.password});

  final String email;
  final String password;

  Map<String, dynamic> toJson() => {'email': email, 'password': password};
}

class RegisterRequest {
  RegisterRequest({
    required this.name,
    required this.email,
    required this.password,
    this.phone,
  });

  final String name;
  final String email;
  final String password;
  final String? phone;

  Map<String, dynamic> toJson() => {
    'name': name.trim(),
    'email': email.trim(),
    'password': password,
    if (phone != null && phone!.trim().isNotEmpty) 'phone': phone!.trim(),
  };
}

class UserProfile {
  UserProfile({
    required this.id,
    required this.email,
    required this.name,
    required this.role,
    this.phone,
  });

  final int id;
  final String email;
  final String name;
  final String role;
  final String? phone;

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      id: json['id'] as int,
      email: json['email'] as String,
      name: json['name'] as String,
      role: json['role'] as String,
      phone: json['phone'] as String?,
    );
  }
}

class AdvisorLicense {
  AdvisorLicense({
    required this.id,
    required this.state,
    required this.licenseNumber,
    required this.verificationStatus,
    this.licenseType,
    this.rejectionReason,
  });

  final int id;
  final String state;
  final String licenseNumber;
  final String verificationStatus;
  final String? licenseType;
  final String? rejectionReason;

  factory AdvisorLicense.fromJson(Map<String, dynamic> json) {
    return AdvisorLicense(
      id: json['id'] as int,
      state: (json['state'] as String? ?? 'NA').toUpperCase(),
      licenseNumber: json['license_number'] as String? ?? '',
      verificationStatus: json['verification_status'] as String? ?? 'pending',
      licenseType: json['license_type'] as String?,
      rejectionReason: json['rejection_reason'] as String?,
    );
  }
}
