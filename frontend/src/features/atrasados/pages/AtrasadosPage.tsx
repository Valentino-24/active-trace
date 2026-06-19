import { useQuery } from '@tanstack/react-query';
import api from '@/shared/services/api';

export default function AtrasadosPage() {
  // Get user's asignaciones to find materia and cohorte
  const { data: equipos } = useQuery({
    queryKey: ['mi-equipo'],
    queryFn: () => api.get('/equipos/mi-equipo').then(r => r.data),
  });

  const materiaId = equipos?.items?.[0]?.materia?.id;
  const cohorteId = equipos?.items?.[0]?.cohorte?.id;

  const { data, isLoading, error } = useQuery({
    queryKey: ['atrasados', materiaId, cohorteId],
    queryFn: () => api.get('/analisis/atrasados', {
      params: { materia_id: materiaId, cohorte_id: cohorteId },
    }).then(r => r.data),
    enabled: !!materiaId && !!cohorteId,
  });

  if (!materiaId) return <p className="text-gray-500 p-4">Cargando datos del equipo...</p>;
  if (isLoading) return <p>Cargando atrasados...</p>;
  if (error) return <p className="text-red-600">Error al cargar atrasados</p>;
  if (!data?.items?.length) return <p className="text-green-600 p-4">Sin alumnos atrasados en tu materia</p>;

  const items = data.items;
  const total = items.length;
  const promedio = items.reduce((s: number, a: any) => s + a.dias_atraso, 0) / total;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Alumnos Atrasados</h1>
      <div className="flex gap-4">
        <div className="bg-white p-4 rounded shadow flex-1">
          <p className="text-2xl font-bold">{total}</p>
          <p className="text-sm text-gray-500">Total atrasados</p>
        </div>
        <div className="bg-white p-4 rounded shadow flex-1">
          <p className="text-2xl font-bold">{promedio.toFixed(1)}</p>
          <p className="text-sm text-gray-500">Promedio días atraso</p>
        </div>
      </div>
      <table className="min-w-full bg-white rounded shadow">
        <thead className="bg-gray-100">
          <tr>
            <th className="text-left p-2">Alumno</th>
            <th className="text-left p-2">Pendientes</th>
            <th className="text-left p-2">Días atraso</th>
          </tr>
        </thead>
        <tbody>
          {items.map((a: any) => (
            <tr key={a.id || a.alumno_id} className="border-t">
              <td className="p-2">{a.alumno_nombre || a.alumno_id}</td>
              <td className="p-2">{a.entregas_pendientes}</td>
              <td className="p-2">{a.dias_atraso}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
