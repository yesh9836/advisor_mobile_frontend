import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const initMock = vi.fn();
const getClientMock = vi.fn();
const captureExceptionMock = vi.fn();
const withScopeMock = vi.fn();

vi.mock("@sentry/react", () => ({
  init: initMock,
  getClient: getClientMock,
  captureException: captureExceptionMock,
  withScope: withScopeMock,
}));

describe("sentry helpers", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    initMock.mockReset();
    getClientMock.mockReset();
    captureExceptionMock.mockReset();
    withScopeMock.mockReset();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("does not initialize when DSN is missing", async () => {
    const { initSentry } = await import("@/lib/sentry");
    initSentry();
    expect(initMock).not.toHaveBeenCalled();
  });

  it("initializes once when DSN is configured", async () => {
    vi.stubEnv("VITE_SENTRY_DSN", "https://public@example.ingest.sentry.io/1");
    vi.stubEnv("VITE_SENTRY_ENVIRONMENT", "staging");
    vi.stubEnv("VITE_SENTRY_RELEASE", "frontend@1.2.3");
    vi.stubEnv("VITE_SENTRY_TRACES_SAMPLE_RATE", "0.25");

    const { initSentry } = await import("@/lib/sentry");
    initSentry();
    initSentry();

    expect(initMock).toHaveBeenCalledTimes(1);
    expect(initMock).toHaveBeenCalledWith(
      expect.objectContaining({
        dsn: "https://public@example.ingest.sentry.io/1",
        environment: "staging",
        release: "frontend@1.2.3",
        tracesSampleRate: 0.25,
      }),
    );
  });

  it("captures UI exceptions only when a Sentry client exists", async () => {
    const scopeSetContext = vi.fn();
    withScopeMock.mockImplementation((callback: (scope: { setContext: typeof scopeSetContext }) => void) =>
      callback({ setContext: scopeSetContext }),
    );

    const { captureUiException } = await import("@/lib/sentry");
    const error = new Error("boom");

    getClientMock.mockReturnValue(null);
    captureUiException(error, { componentStack: "StackA" });
    expect(captureExceptionMock).not.toHaveBeenCalled();

    getClientMock.mockReturnValue({});
    captureUiException(error, { componentStack: "StackB" });
    expect(scopeSetContext).toHaveBeenCalledWith("react", { componentStack: "StackB" });
    expect(captureExceptionMock).toHaveBeenCalledTimes(1);
    expect(captureExceptionMock).toHaveBeenCalledWith(error);
  });
});
