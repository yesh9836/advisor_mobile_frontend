import { describe, expect, it } from "vitest";

import { buildAppPath, isAuthRoutePath, normalizeAppBasePath } from "@/lib/app-path";

describe("app path helpers", () => {
  it("normalizes base paths to leading-slash form without trailing slash", () => {
    expect(normalizeAppBasePath(undefined)).toBe("/");
    expect(normalizeAppBasePath("")).toBe("/");
    expect(normalizeAppBasePath("portal/")).toBe("/portal");
    expect(normalizeAppBasePath("/portal/")).toBe("/portal");
  });

  it("builds absolute app paths for root and subpath deployments", () => {
    expect(buildAppPath("/login", "/")).toBe("/login");
    expect(buildAppPath("/login", "/portal")).toBe("/portal/login");
    expect(buildAppPath("/", "/portal")).toBe("/portal");
  });

  it("detects auth routes for the configured base path", () => {
    expect(isAuthRoutePath("/portal/login", "/portal")).toBe(true);
    expect(isAuthRoutePath("/portal/register/", "/portal")).toBe(true);
    expect(isAuthRoutePath("/portal/forgot-password", "/portal")).toBe(true);
    expect(isAuthRoutePath("/portal/reset-password", "/portal")).toBe(true);
    expect(isAuthRoutePath("/login", "/portal")).toBe(false);
  });
});
