import { useCalificaciones } from '../hooks/useCalificaciones';

export default function TablaNotas({ materiaId }: { materiaId: string }) {
  const { data, isLoading, error } = useCalificaciones(materiaId);

  if (isLoading) return <p>Cargando notas...</p>;
  if (error) return <p className="text-red-600">Error al cargar notas</p>;
  if (!data?.length) return <p>Sin calificaciones registradas</p>;

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full bg-white rounded shadow">
        <thead className="bg-gray-100">
          <tr>
            <th className="text-left p-2">Alumno</th>
            <th className="text-left p-2">Actividad</th>
            <th className="text-left p-2">Nota</th>
            <th className="text-left p-2">Estado</th>
          </tr>
        </thead>
        <tbody>
          {data.map((c, i) => (
            <tr key={i} className="border-t">
              <td className="p-2">{c.alumno_id}</td>
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
