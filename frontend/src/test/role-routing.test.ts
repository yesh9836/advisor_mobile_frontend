import { describe, expect, it } from "vitest";

import { getHomeRouteByRole } from "@/utils/role-routing";

describe("getHomeRouteByRole", () => {
  it("returns admin dashboard route for admin role", () => {
    expect(getHomeRouteByRole("admin")).toBe("/admin");
  });

  it("returns advisor dashboard route for advisor role", () => {
    expect(getHomeRouteByRole("advisor")).toBe("/dashboard");
  });

  it("defaults to advisor dashboard route for unknown roles", () => {
    expect(getHomeRouteByRole("manager")).toBe("/dashboard");
    expect(getHomeRouteByRole(undefined)).toBe("/dashboard");
    expect(getHomeRouteByRole(null)).toBe("/dashboard");
  });
});
