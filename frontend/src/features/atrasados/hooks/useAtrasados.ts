import { useQuery } from '@tanstack/react-query';
import api from '@/shared/services/api';

export interface Atrasado {
  id: string;
  alumno_id: string;
  alumno_nombre: string;
  materia: string;
  entregas_pendientes: number;
  dias_atraso: number;
}

export function useAtrasados(materiaId?: string) {
  return useQuery<Atrasado[]>({
    queryKey: ['atrasados', materiaId],
    queryFn: () => api.get('/analisis/atrasados', { params: { materia_id: materiaId } }).then(r => r.data),
    enabled: !!materiaId,
  });
}
