import {
  AxiosError,
  AxiosHeaders,
  type AxiosRequestConfig,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import { afterEach, describe, expect, it } from "vitest";

import apiClient, { isTerminalRefreshFailure } from "@/api/client";

const originalAdapter = apiClient.defaults.adapter;

const getHeader = (
  headers: AxiosRequestConfig["headers"] | undefined,
  headerName: string,
): string | undefined => {
  if (!headers) {
    return undefined;
  }

  if (headers instanceof AxiosHeaders) {
    const value = headers.get(headerName);
    return typeof value === "string" ? value : undefined;
  }

  const normalizedName = headerName.toLowerCase();
  for (const [key, value] of Object.entries(headers)) {
    if (key.toLowerCase() === normalizedName && typeof value === "string") {
      return value;
    }
  }

  return undefined;
};

const installCaptureAdapter = () => {
  const seen: InternalAxiosRequestConfig[] = [];
  apiClient.defaults.adapter = async (
    config: InternalAxiosRequestConfig,
  ): Promise<AxiosResponse> => {
    seen.push(config);
    return {
      data: { ok: true },
      status: 200,
      statusText: "OK",
      headers: {},
      config,
    };
  };
  return seen;
};

const buildAxiosError = (statusCode?: number): AxiosError => {
  const config = {
    headers: new AxiosHeaders(),
  } as InternalAxiosRequestConfig;
  if (statusCode === undefined) {
    return new AxiosError("network failure", "ERR_NETWORK", config);
  }
  return new AxiosError(
    `Request failed with status code ${statusCode}`,
    "ERR_BAD_RESPONSE",
    config,
    undefined,
    {
      data: {},
      status: statusCode,
      statusText: `${statusCode}`,
      headers: {},
      config,
    } as AxiosResponse,
  );
};

afterEach(() => {
  apiClient.defaults.adapter = originalAdapter;
  document.cookie = "csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
  localStorage.clear();
});

describe("apiClient auth transport", () => {
  it("does not inject Authorization headers from localStorage", async () => {
    localStorage.setItem("access_token", "legacy-token");
    const seen = installCaptureAdapter();

    await apiClient.get("/leads");

    const authorization = getHeader(seen[0]?.headers, "Authorization");
    expect(authorization).toBeUndefined();
  });

  it("adds CSRF header for mutating requests only", async () => {
    document.cookie = "csrf_token=test-csrf-token; path=/";
    const seen = installCaptureAdapter();

    await apiClient.post("/purchases/checkout", { package_id: 1 });
    await apiClient.get("/auth/me");

    const postCsrf = getHeader(seen[0]?.headers, "X-CSRF-Token");
    const getCsrf = getHeader(seen[1]?.headers, "X-CSRF-Token");

    expect(postCsrf).toBe("test-csrf-token");
    expect(getCsrf).toBeUndefined();
  });

  it("classifies only 401/403 refresh failures as terminal", () => {
    expect(isTerminalRefreshFailure(buildAxiosError(401))).toBe(true);
    expect(isTerminalRefreshFailure(buildAxiosError(403))).toBe(true);
    expect(isTerminalRefreshFailure(buildAxiosError(500))).toBe(false);
    expect(isTerminalRefreshFailure(buildAxiosError())).toBe(false);
    expect(isTerminalRefreshFailure(new Error("plain error"))).toBe(false);
  });
});
