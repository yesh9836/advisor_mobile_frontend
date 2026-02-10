export type LicenseVerificationStatus = "pending" | "verified" | "rejected";

export interface License {
  id: number;
  user_id: number;
  state: string;
  license_number: string;
  license_type: string | null;
  document_path: string | null;
  verification_status: LicenseVerificationStatus;
  verified_at: string | null;
  verified_by: number | null;
  rejection_reason: string | null;
  created_at: string;
}

export interface LicenseCreate {
  state: string;
  license_number: string;
  license_type?: string;
}
