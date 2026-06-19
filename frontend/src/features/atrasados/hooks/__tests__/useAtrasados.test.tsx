import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAtrasados } from '../useAtrasados';

vi.mock('@/shared/services/api', () => ({
  default: {
    get: vi.fn().mockResolvedValue({
      data: [
        { id: '1', alumno_id: 'a1', alumno_nombre: 'Juan', materia: 'Prog I', entregas_pendientes: 2, dias_atraso: 5 },
      ],
    }),
  },
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  setLogoutHandler: vi.fn(),
}));

describe('useAtrasados', () => {
  it('fetches atrasados', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useAtrasados('m1'), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.length).toBe(1);
    expect(result.current.data?.[0].alumno_nombre).toBe('Juan');
  });
});
