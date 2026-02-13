import type { UserRole } from "@/types/auth";

export const getHomeRouteByRole = (role: UserRole | null | undefined): string => {
  if (role === "admin") {
    return "/admin";
  }

  return "/dashboard";
};
