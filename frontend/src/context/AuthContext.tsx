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
import { AUTH_LOGOUT_EVENT } from "@/api/client";
import type { LoginCredentials, RegisterData, User } from "@/types/auth";
import { getApiErrorMessage } from "@/utils/api-error";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  error: string | null;
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<User>;
  logout: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider = ({ children }: PropsWithChildren) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    setLoading(true);
    setError(null);

    try {
      await loginUser(credentials);
      const currentUser = await getCurrentUser();
      setUser(currentUser);
    } catch (err) {
      setUser(null);
      const message = getApiErrorMessage(err, "Request failed");
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
      const message = getApiErrorMessage(err, "Request failed");
      setError(message);
      throw new Error(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    await logoutUser();
    setUser(null);
    setError(null);
  }, []);

  useEffect(() => {
    let isMounted = true;

    const bootstrapAuth = async () => {
      try {
        const currentUser = await getCurrentUser();
        if (isMounted) {
          setUser(currentUser);
        }
      } catch {
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
