import axios from "axios";

type ApiErrorDetail = string | Array<{ msg?: string | null }>;

interface ApiErrorPayload {
  detail?: ApiErrorDetail;
}

export const getApiErrorMessage = (error: unknown, fallback: string): string => {
  if (axios.isAxiosError<ApiErrorPayload>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }

    if (Array.isArray(detail) && detail.length > 0) {
      return detail
        .map((item) => item.msg?.trim() || "Validation error")
        .join(", ");
    }

    return error.message || fallback;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
};
