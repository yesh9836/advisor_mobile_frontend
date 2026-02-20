import { z } from "zod";

export class ApiContractError extends Error {
  endpoint: string;

  constructor(endpoint: string, issues: string[]) {
    const issueSummary =
      issues.length > 0 ? ` (${issues.slice(0, 3).join("; ")})` : "";
    super(`Unexpected response format from ${endpoint}${issueSummary}`);
    this.name = "ApiContractError";
    this.endpoint = endpoint;
  }
}

const formatIssuePath = (path: readonly PropertyKey[]): string => {
  if (path.length === 0) {
    return "<root>";
  }
  return path.map((segment) => String(segment)).join(".");
};

export const parseApiContract = <T>(
  schema: z.ZodType<T>,
  payload: unknown,
  endpoint: string,
): T => {
  const parsed = schema.safeParse(payload);
  if (parsed.success) {
    return parsed.data;
  }

  const issues = parsed.error.issues.map(
    (issue) => `${formatIssuePath(issue.path)}: ${issue.message}`,
  );
  console.error("API contract validation failed", {
    endpoint,
    issues,
  });
  throw new ApiContractError(endpoint, issues);
};
