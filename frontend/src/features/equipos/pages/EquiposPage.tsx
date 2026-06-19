import { useQuery } from '@tanstack/react-query';
import api from '@/shared/services/api';

export default function EquiposPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['equipos'],
    queryFn: () => api.get('/equipos/mis-equipos').then(r => r.data),
  });

  return (
    <div>
      <h1 className="text-xl font-bold mb-4">Equipos Docentes</h1>
      {isLoading ? <p>Cargando...</p> : (
        <div className="bg-white rounded shadow p-4">
          <p className="text-gray-600">Equipos cargados: {data?.length ?? 0}</p>
        </div>
      )}
    </div>
  );
}
