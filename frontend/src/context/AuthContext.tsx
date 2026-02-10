import axios from "axios";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import {
  getCurrentUser,
  login as loginUser,
  logout as logoutUser,
  register as registerUser,
} from "@/api/auth";
import { ACCESS_TOKEN_KEY, AUTH_LOGOUT_EVENT } from "@/api/client";
import type { LoginCredentials, RegisterData, User } from "@/types/auth";
import type { ApiError } from "@/types/common";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  error: string | null;
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<User>;
  logout: () => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const parseErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError<ApiError>(error)) {
    const detail = error.response?.data?.detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((issue) => issue.msg).join(", ");
    }

    return error.message || "Request failed";
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Unexpected error";
};

export const AuthProvider = ({ children }: PropsWithChildren) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    setLoading(true);
    setError(null);

    try {
      const token = await loginUser(credentials);
      localStorage.setItem(ACCESS_TOKEN_KEY, token.access_token);

      const currentUser = await getCurrentUser();
      setUser(currentUser);
    } catch (err) {
      logoutUser();
      const message = parseErrorMessage(err);
      setError(message);
      throw new Error(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const register = useCallback(async (data: RegisterData): Promise<User> => {
    setLoading(true);
    setError(null);

    try {
      return await registerUser(data);
    } catch (err) {
      const message = parseErrorMessage(err);
      setError(message);
      throw new Error(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    logoutUser();
    setUser(null);
    setError(null);
  }, []);

  useEffect(() => {
    let isMounted = true;

    const bootstrapAuth = async () => {
      const token = localStorage.getItem(ACCESS_TOKEN_KEY);

      if (!token) {
        if (isMounted) {
          setLoading(false);
        }
        return;
      }

      try {
        const currentUser = await getCurrentUser();
        if (isMounted) {
          setUser(currentUser);
        }
      } catch {
        logoutUser();
        if (isMounted) {
          setUser(null);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    const handleForcedLogout = () => {
      if (isMounted) {
        setUser(null);
        setError(null);
        setLoading(false);
      }
    };

    void bootstrapAuth();
    window.addEventListener(AUTH_LOGOUT_EVENT, handleForcedLogout);

    return () => {
      isMounted = false;
      window.removeEventListener(AUTH_LOGOUT_EVENT, handleForcedLogout);
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      error,
      isAuthenticated: Boolean(user),
      login,
      register,
      logout,
      clearError,
    }),
    [user, loading, error, login, register, logout, clearError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return context;
};
