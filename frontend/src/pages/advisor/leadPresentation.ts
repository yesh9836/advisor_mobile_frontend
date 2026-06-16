import type { Lead, LeadOutcomeStatus } from "@/types/lead";

export type LeadStage = "New" | "Contacted" | "Appointment Set" | "Closed Deal";

export const toDisplayStage = (
  status: LeadOutcomeStatus | null | undefined,
): LeadStage => {
  if (status === "contacted") return "Contacted";
  if (status === "appointment_set") return "Appointment Set";
  if (status === "closed_deal") return "Closed Deal";
  return "New";
};

export const toInitials = (
  firstName: string | null,
  lastName: string | null,
): string => {
  const first = firstName?.trim()?.[0] ?? "";
  const last = lastName?.trim()?.[0] ?? "";
  const initials = `${first}${last}`.toUpperCase();
  return initials || "NA";
};

export const toDisplayName = (lead: Lead): string => {
  const first = lead.first_name?.trim() ?? "";
  const last = lead.last_name?.trim() ?? "";
  const full = `${first} ${last}`.trim();
  return full || "Unknown Lead";
};

export const formatDateTime = (value: string): string => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Recently";
  }

  const datePart = parsed.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  const timePart = parsed.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });

  return `${datePart} • ${timePart}`;
};

export const stageClassName = (stage: LeadStage): string => {
  if (stage === "New") return "badge badge-new";
  if (stage === "Contacted") return "badge badge-contacted";
  if (stage === "Appointment Set") return "badge badge-set";
  return "badge badge-closed";
};
