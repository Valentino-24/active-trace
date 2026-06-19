import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ProtectedRoute from '../ProtectedRoute';

// Mock useAuth
const mockUseAuth = vi.fn();
vi.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

describe('ProtectedRoute', () => {
  it('shows loading spinner when loading', () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false, isLoading: true, hasPermission: () => false });
    render(<MemoryRouter><ProtectedRoute><div>Content</div></ProtectedRoute></MemoryRouter>);
    expect(screen.getByText('Cargando...')).toBeDefined();
  });

  it('redirects to login when not authenticated', () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false, isLoading: false, hasPermission: () => false });
    render(<MemoryRouter><ProtectedRoute><div>Content</div></ProtectedRoute></MemoryRouter>);
    expect(screen.queryByText('Content')).toBeNull();
  });

  it('renders children when authenticated without permission check', () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true, isLoading: false, hasPermission: () => true });
    render(<MemoryRouter><ProtectedRoute><div>Content</div></ProtectedRoute></MemoryRouter>);
    expect(screen.getByText('Content')).toBeDefined();
  });

  it('redirects to 403 when missing required permission', () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true, isLoading: false, hasPermission: () => false });
    render(<MemoryRouter><ProtectedRoute permission="admin:ver"><div>Content</div></ProtectedRoute></MemoryRouter>);
    expect(screen.queryByText('Content')).toBeNull();
  });
});
