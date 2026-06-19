import React, { createContext, useContext, useReducer, useEffect, useCallback } from 'react';
import api, { setTokens, clearTokens, setLogoutHandler } from '@/shared/services/api';
import type { User, AuthState } from '@/shared/types/auth';

type AuthAction =
  | { type: 'LOGIN_START' }
  | { type: 'LOGIN_SUCCESS'; payload: { user: User; access: string; refresh: string } }
  | { type: 'LOGOUT' }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'TWO_FACTOR_REQUIRED'; payload: string };

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasPermission: (perm: string) => boolean;
  twoFactorToken: string | null;
}

const AuthContext = createContext<AuthContextType | null>(null);

const initialState: AuthState & { twoFactorToken: string | null } = {
  user: null,
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isLoading: true,
  twoFactorToken: null,
};

function authReducer(state: typeof initialState, action: AuthAction): typeof initialState {
  switch (action.type) {
    case 'LOGIN_START':
      return { ...state, isLoading: true };
    case 'LOGIN_SUCCESS':
      return {
        ...state,
        user: action.payload.user,
        accessToken: action.payload.access,
        refreshToken: action.payload.refresh,
        isAuthenticated: true,
        isLoading: false,
      };
    case 'LOGOUT':
      return { ...initialState, isLoading: false };
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'TWO_FACTOR_REQUIRED':
      return { ...state, isLoading: false, twoFactorToken: action.payload };
    default:
      return state;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(authReducer, initialState);

  const logout = useCallback(() => {
    clearTokens();
    dispatch({ type: 'LOGOUT' });
  }, []);

  useEffect(() => {
    setLogoutHandler(logout);
  }, [logout]);

  // Try to restore session from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem('auth');
    if (stored) {
      try {
        const { access, refresh } = JSON.parse(stored);
        setTokens(access, refresh);
        api.get('/auth/me').then(({ data }) => {
          dispatch({ type: 'LOGIN_SUCCESS', payload: { user: data, access, refresh } });
        }).catch(() => {
          localStorage.removeItem('auth');
          dispatch({ type: 'SET_LOADING', payload: false });
        });
      } catch {
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    } else {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, []);

  const login = async (email: string, password: string) => {
    dispatch({ type: 'LOGIN_START' });
    const { data } = await api.post('/auth/login', { email, password });
    if (data.two_factor_required) {
      dispatch({ type: 'TWO_FACTOR_REQUIRED', payload: data.temp_token });
      return;
    }
    setTokens(data.access_token, data.refresh_token);
    localStorage.setItem('auth', JSON.stringify({ access: data.access_token, refresh: data.refresh_token }));
    const me = await api.get('/auth/me');
    dispatch({ type: 'LOGIN_SUCCESS', payload: { user: me.data, access: data.access_token, refresh: data.refresh_token } });
  };

  const hasPermission = (perm: string) => state.user?.permissions?.includes(perm) ?? false;

  return (
    <AuthContext.Provider value={{ ...state, login, logout, hasPermission }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
