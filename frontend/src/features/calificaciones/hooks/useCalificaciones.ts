import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { calificacionesService, type Calificacion } from '../types/calificaciones';

export function useCalificaciones(materiaId?: string) {
  return useQuery<Calificacion[]>({
    queryKey: ['calificaciones', materiaId],
    queryFn: () => calificacionesService.listar(materiaId || '').then(r => r.data),
  });
}

export function useImportarCalificaciones() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (formData: FormData) => calificacionesService.importar(formData),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['calificaciones'] }),
  });
}
