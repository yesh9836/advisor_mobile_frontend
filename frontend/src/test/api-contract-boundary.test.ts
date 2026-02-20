import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  AUTH_LOGOUT_EVENT: "auth:logout",
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

import apiClient from "@/api/client";
import { getCurrentUser } from "@/api/auth";
import { getLeads } from "@/api/leads";
import { getPackages } from "@/api/purchases";

type MockFn = ReturnType<typeof vi.fn>;

const mockedApiClient = apiClient as unknown as {
  get: MockFn;
  post: MockFn;
  put: MockFn;
};

describe("API contract boundary guards", () => {
  beforeEach(() => {
    mockedApiClient.get.mockReset();
    mockedApiClient.post.mockReset();
    mockedApiClient.put.mockReset();
  });

  it("rejects malformed auth payloads at /auth/me", async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        email: "advisor@example.com",
      },
    });

    await expect(getCurrentUser()).rejects.toThrow(
      "Unexpected response format from /auth/me",
    );
  });

  it("parses valid purchase package payloads", async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: [
        {
          id: 1,
          name: "Starter",
          price_cents: 20000,
          currency: "USD",
          state_limit: 2,
          daily_download_limit: 10,
          features: ["10 leads"],
          stripe_price_id: "price_starter",
          created_at: "2026-02-20T00:00:00Z",
        },
      ],
    });

    await expect(getPackages()).resolves.toEqual([
      {
        id: 1,
        name: "Starter",
        price_cents: 20000,
        currency: "USD",
        state_limit: 2,
        daily_download_limit: 10,
        features: ["10 leads"],
        stripe_price_id: "price_starter",
        created_at: "2026-02-20T00:00:00Z",
      },
    ]);
  });

  it("rejects malformed lead collection payloads", async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        items: {},
        total: 0,
        page: 1,
        size: 25,
      },
    });

    await expect(getLeads(1, 25)).rejects.toThrow(
      "Unexpected response format from /leads",
    );
  });
});
