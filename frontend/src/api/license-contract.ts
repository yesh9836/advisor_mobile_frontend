import type { AdminLicenseDecisionRow, License, LicenseWithUser } from "@/types/license";
import { z } from "zod";

const baseLicenseSchema = z
  .looseObject({
    id: z.number(),
    user_id: z.number(),
    state: z.string(),
    license_number: z.string(),
    license_type: z.string().nullable(),
    has_document: z.boolean(),
    verification_status: z.enum(["pending", "verified", "rejected"]),
    verified_at: z.string().nullable(),
    verified_by: z.number().nullable(),
    rejection_reason: z.string().nullable(),
    created_at: z.string(),
  });

export const licenseSchema: z.ZodType<License> = baseLicenseSchema;

export const licenseWithUserSchema: z.ZodType<LicenseWithUser> =
  baseLicenseSchema.extend({
  user_name: z.string(),
  user_email: z.string(),
});

export const adminLicenseDecisionRowSchema: z.ZodType<AdminLicenseDecisionRow> = z
  .looseObject({
    license_id: z.number(),
    user_id: z.number(),
    user_name: z.string(),
    user_email: z.string(),
    state: z.string(),
    license_number: z.string(),
    license_type: z.string().nullable(),
    decision_status: z.enum(["verified", "rejected"]),
    decision_at: z.string().nullable(),
    submission_type: z.enum(["first_time", "resubmission"]),
    review_cycle: z.number(),
    rejection_reason: z.string().nullable(),
    created_at: z.string(),
  });
