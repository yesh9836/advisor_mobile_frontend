import axios from "axios";
import { useCallback, useEffect, useRef } from "react";

export const isRequestCanceled = (error: unknown): boolean => {
  if (axios.isCancel(error)) {
    return true;
  }

  if (error instanceof DOMException && error.name === "AbortError") {
    return true;
  }

  const maybeError = error as { code?: unknown } | null;
  return maybeError?.code === "ERR_CANCELED";
};

export const useLatestRequest = () => {
  const requestIdRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);

  const beginRequest = useCallback(() => {
    requestIdRef.current += 1;
    controllerRef.current?.abort();
    controllerRef.current = new AbortController();

    return {
      requestId: requestIdRef.current,
      signal: controllerRef.current.signal,
    };
  }, []);

  const isLatestRequest = useCallback(
    (requestId: number) => requestIdRef.current === requestId,
    [],
  );

  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
    };
  }, []);

  return {
    beginRequest,
    isLatestRequest,
  };
};
