import { useQuery } from '@tanstack/react-query';
import api from '@/shared/services/api';

export default function TablaNotas() {
  const { data: equipos } = useQuery({
    queryKey: ['mi-equipo'],
    queryFn: () => api.get('/equipos/mi-equipo').then(r => r.data),
  });

  const materiaId = equipos?.items?.[0]?.materia?.id;
  const cohorteId = equipos?.items?.[0]?.cohorte?.id;

  const { data, isLoading, error } = useQuery({
    queryKey: ['calificaciones', materiaId, cohorteId],
    queryFn: () => api.get('/calificaciones', {
      params: { materia_id: materiaId, cohorte_id: cohorteId },
    }).then(r => r.data),
    enabled: !!materiaId && !!cohorteId,
  });

  if (!materiaId) return <p className="text-gray-500 p-4">Cargando datos del equipo...</p>;
  if (isLoading) return <p>Cargando notas...</p>;
  if (error) return <p className="text-red-600">Error al cargar notas</p>;
  if (!data?.items?.length) return <p className="p-4">Sin calificaciones registradas</p>;

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full bg-white rounded shadow">
        <thead className="bg-gray-100">
          <tr>
            <th className="text-left p-2">Actividad</th>
            <th className="text-left p-2">Nota</th>
            <th className="text-left p-2">Estado</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((c: any, i: number) => (
            <tr key={i} className="border-t">
              <td className="p-2">{c.actividad}</td>
              <td className="p-2">{c.nota}</td>
              <td className="p-2">{c.estado}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
