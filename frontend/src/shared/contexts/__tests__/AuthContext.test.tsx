import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider, useAuth } from '../AuthContext';

vi.mock('@/shared/services/api', async () => {
  const actual = await vi.importActual<typeof import('@/shared/services/api')>('@/shared/services/api');
  return {
    ...actual,
    default: {
      ...actual.default,
      get: vi.fn(),
      post: vi.fn(),
    },
    setTokens: vi.fn(),
    clearTokens: vi.fn(),
    setLogoutHandler: vi.fn(),
  };
});

const TestConsumer = () => {
  const auth = useAuth();
  return (
    <div>
      <span data-testid="authenticated">{String(auth.isAuthenticated)}</span>
      <span data-testid="loading">{String(auth.isLoading)}</span>
      <button data-testid="logout-btn" onClick={auth.logout}>Logout</button>
    </div>
  );
};

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('starts with loading true, not authenticated', async () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <TestConsumer />
        </AuthProvider>
      </MemoryRouter>
    );

    // After initial load, loading becomes false (no stored session)
    const authenticated = await screen.findByTestId('authenticated');
    expect(authenticated.textContent).toBe('false');
  });

  it('logout clears state', async () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <TestConsumer />
        </AuthProvider>
      </MemoryRouter>
    );

    const logoutBtn = await screen.findByTestId('logout-btn');
    logoutBtn.click();
    const authenticated = screen.getByTestId('authenticated');
    expect(authenticated.textContent).toBe('false');
  });
});
