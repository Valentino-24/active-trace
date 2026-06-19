import api from '@/shared/services/api';

export interface Calificacion {
  id: string;
  alumno_id: string;
  materia_id: string;
  actividad: string;
  nota: number;
  estado: string;
}

export const calificacionesService = {
  listar: (materiaId: string) => api.get<Calificacion[]>(`/calificaciones?materia_id=${materiaId}`),
  importar: (formData: FormData) => api.post('/calificaciones/importar', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
};
