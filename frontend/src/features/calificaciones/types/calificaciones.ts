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
  listar: (materiaId?: string) => {
    const params = materiaId ? { materia_id: materiaId } : {};
    return api.get<Calificacion[]>('/calificaciones', { params });
  },
  importar: (formData: FormData) => api.post('/calificaciones/importar', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
};
