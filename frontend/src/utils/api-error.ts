import axios from "axios";

type ApiErrorDetailObject = {
  code?: string | null;
  message?: string | null;
  available_count?: number | null;
  required_count?: number | null;
};

type ApiErrorDetail = string | ApiErrorDetailObject | Array<{ msg?: string | null }>;

interface ApiErrorPayload {
  detail?: ApiErrorDetail;
}

export interface ParsedApiError {
  message: string;
  code: string | null;
}

export const parseApiError = (error: unknown, fallback: string): ParsedApiError => {
  if (axios.isAxiosError<ApiErrorPayload>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") {
      return { message: detail, code: null };
    }

    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      const message = typeof detail.message === "string" && detail.message.trim()
        ? detail.message.trim()
        : fallback;
      const code = typeof detail.code === "string" && detail.code.trim()
        ? detail.code.trim()
        : null;
      return { message, code };
    }

    if (Array.isArray(detail) && detail.length > 0) {
      const message = detail
        .map((item) => item.msg?.trim() || "Validation error")
        .join(", ");
      return { message, code: null };
    }

    return { message: error.message || fallback, code: null };
  }

  if (error instanceof Error) {
    return { message: error.message, code: null };
  }

  return { message: fallback, code: null };
};

export const getApiErrorMessage = (error: unknown, fallback: string): string => {
  return parseApiError(error, fallback).message;
};
