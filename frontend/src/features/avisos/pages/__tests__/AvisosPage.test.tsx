import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useQuery } from '@tanstack/react-query';
import api from '@/shared/services/api';

vi.mock('@/shared/services/api', () => ({
  default: { get: vi.fn().mockResolvedValue({ data: { total: 3 } }) },
  setTokens: vi.fn(), clearTokens: vi.fn(), setLogoutHandler: vi.fn(),
}));

describe('Coordinacion pages fetch', () => {
  it('fetches avisos', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() =>
      useQuery({ queryKey: ['avisos'], queryFn: () => api.get('/avisos').then(r => r.data) }),
    { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.total).toBe(3);
  });
});
