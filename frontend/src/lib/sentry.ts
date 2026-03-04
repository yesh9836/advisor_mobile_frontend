import * as Sentry from "@sentry/react";

const parseSampleRate = (value: string | undefined, fallback: number): number => {
  if (!value) {
    return fallback;
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return fallback;
  }
  if (parsed < 0) {
    return 0;
  }
  if (parsed > 1) {
    return 1;
  }
  return parsed;
};

const normalizeOptional = (value: string | undefined): string | undefined => {
  const normalized = value?.trim();
  return normalized ? normalized : undefined;
};

let initialized = false;

export const initSentry = (): void => {
  if (initialized) {
    return;
  }

  const dsn = normalizeOptional(import.meta.env.VITE_SENTRY_DSN);
  if (!dsn) {
    return;
  }

  Sentry.init({
    dsn,
    environment: normalizeOptional(import.meta.env.VITE_SENTRY_ENVIRONMENT) ?? import.meta.env.MODE,
    release: normalizeOptional(import.meta.env.VITE_SENTRY_RELEASE),
    tracesSampleRate: parseSampleRate(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE, 0),
    attachStacktrace: true,
  });

  initialized = true;
};

export const captureUiException = (
  error: Error,
  context: { componentStack?: string } = {},
): void => {
  const client = Sentry.getClient();
  if (!client) {
    return;
  }
  Sentry.withScope((scope) => {
    if (context.componentStack) {
      scope.setContext("react", { componentStack: context.componentStack });
    }
    Sentry.captureException(error);
  });
};
