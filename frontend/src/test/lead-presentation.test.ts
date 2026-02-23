import { describe, expect, it } from "vitest";

import {
  formatDateTime,
  stageClassName,
  toDisplayName,
  toDisplayStage,
  toInitials,
} from "@/pages/advisor/leadPresentation";
import type { Lead } from "@/types/lead";

describe("leadPresentation helpers", () => {
  it("maps lead outcome statuses to display stages", () => {
    expect(toDisplayStage("new")).toBe("New");
    expect(toDisplayStage("contacted")).toBe("Contacted");
    expect(toDisplayStage("appointment_set")).toBe("Appointment Set");
    expect(toDisplayStage(null)).toBe("New");
  });

  it("builds initials safely for missing names", () => {
    expect(toInitials("Ada", "Lovelace")).toBe("AL");
    expect(toInitials("  ada", null)).toBe("A");
    expect(toInitials(null, null)).toBe("NA");
  });

  it("builds display names with unknown fallback", () => {
    expect(
      toDisplayName({ first_name: "  Ada ", last_name: " Lovelace " } as Lead),
    ).toBe("Ada Lovelace");
    expect(toDisplayName({ first_name: null, last_name: null } as Lead)).toBe(
      "Unknown Lead",
    );
  });

  it("formats invalid and valid timestamps consistently", () => {
    expect(formatDateTime("not-a-date")).toBe("Recently");

    const formatted = formatDateTime("2026-01-15T12:34:00Z");
    expect(formatted).toContain("Jan");
    expect(formatted).toContain("2026");
    expect(formatted).toContain("•");
  });

  it("maps stages to badge class names", () => {
    expect(stageClassName("New")).toBe("badge badge-new");
    expect(stageClassName("Contacted")).toBe("badge badge-contacted");
    expect(stageClassName("Appointment Set")).toBe("badge badge-set");
  });
});
