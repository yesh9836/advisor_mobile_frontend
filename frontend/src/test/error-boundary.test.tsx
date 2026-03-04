import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ErrorBoundary from "@/components/common/ErrorBoundary";
import { captureUiException } from "@/lib/sentry";

vi.mock("@/lib/sentry", () => ({
  captureUiException: vi.fn(),
}));

const ThrowingChild = () => {
  throw new Error("Sensitive internal exception message");
};

describe("ErrorBoundary", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders a generic fallback without exposing raw error messages", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(
      screen.getByText("An unexpected error occurred. Please reload and try again."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Sensitive internal exception message")).not.toBeInTheDocument();
    expect(captureUiException).toHaveBeenCalledTimes(1);
  });
});
