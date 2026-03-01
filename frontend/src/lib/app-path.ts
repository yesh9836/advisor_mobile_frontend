export const normalizePathname = (pathname: string): string => {
  const normalized = pathname.replace(/\/+$/, "");
  return normalized || "/";
};

export const normalizeAppBasePath = (basePath: string | undefined): string => {
  const trimmed = (basePath ?? "").trim();
  if (!trimmed) {
    return "/";
  }
  const withLeadingSlash = trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  return normalizePathname(withLeadingSlash);
};

export const buildAppPath = (routePath: string, basePath: string): string => {
  const normalizedRoute = normalizePathname(routePath.startsWith("/") ? routePath : `/${routePath}`);
  const normalizedBasePath = normalizeAppBasePath(basePath);
  if (normalizedBasePath === "/") {
    return normalizedRoute;
  }
  if (normalizedRoute === "/") {
    return normalizedBasePath;
  }
  return `${normalizedBasePath}${normalizedRoute}`;
};

export const APP_BASE_PATH = normalizeAppBasePath(import.meta.env.VITE_APP_BASE_PATH);
export const APP_LOGIN_PATH = buildAppPath("/login", APP_BASE_PATH);
export const APP_REGISTER_PATH = buildAppPath("/register", APP_BASE_PATH);

export const isAuthRoutePath = (pathname: string, basePath: string = APP_BASE_PATH): boolean => {
  const normalizedPath = normalizePathname(pathname);
  return (
    normalizedPath === buildAppPath("/login", basePath) ||
    normalizedPath === buildAppPath("/register", basePath)
  );
};
