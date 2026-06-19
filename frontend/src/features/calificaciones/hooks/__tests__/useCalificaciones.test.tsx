import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useCalificaciones } from '../useCalificaciones';

vi.mock('@/shared/services/api', () => ({
  default: {
    get: vi.fn().mockResolvedValue({
      data: [
        { id: '1', alumno_id: 'a1', materia_id: 'm1', actividad: 'TP1', nota: 8, estado: 'Aprobado' },
      ],
    }),
  },
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  setLogoutHandler: vi.fn(),
}));

describe('useCalificaciones', () => {
  it('fetches calificaciones', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useCalificaciones('m1'), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.length).toBe(1);
    expect(result.current.data?.[0].actividad).toBe('TP1');
  });
});
