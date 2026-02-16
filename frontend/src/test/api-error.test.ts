import { describe, expect, it } from "vitest";

import { getApiErrorMessage } from "@/utils/api-error";

const makeAxiosError = (options?: {
  message?: string;
  data?: unknown;
}): unknown => {
  return {
    isAxiosError: true,
    message: options?.message ?? "Request failed with status code 400",
    response:
      options && "data" in options
        ? {
            data: options.data,
          }
        : undefined,
  };
};

describe("getApiErrorMessage", () => {
  it("returns string detail from axios payload", () => {
    const error = makeAxiosError({
      data: { detail: "Email already exists" },
    });

    expect(getApiErrorMessage(error, "Fallback")).toBe("Email already exists");
  });

  it("returns joined validation messages from axios array detail", () => {
    const error = makeAxiosError({
      data: {
        detail: [{ msg: "Name is required" }, { msg: "Phone is invalid" }],
      },
    });

    expect(getApiErrorMessage(error, "Fallback")).toBe(
      "Name is required, Phone is invalid",
    );
  });

  it("uses validation fallback for missing or blank issue messages", () => {
    const error = makeAxiosError({
      data: {
        detail: [{ msg: "" }, {}, { msg: "  " }],
      },
    });

    expect(getApiErrorMessage(error, "Fallback")).toBe(
      "Validation error, Validation error, Validation error",
    );
  });

  it("returns axios error message when detail is unavailable", () => {
    const error = makeAxiosError({
      message: "Network Error",
      data: {},
    });

    expect(getApiErrorMessage(error, "Fallback")).toBe("Network Error");
  });

  it("returns normal Error message for non-axios errors", () => {
    expect(getApiErrorMessage(new Error("Something broke"), "Fallback")).toBe(
      "Something broke",
    );
  });

  it("returns fallback for unknown thrown values", () => {
    expect(getApiErrorMessage("badness", "Fallback")).toBe("Fallback");
  });
});
