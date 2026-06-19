import { useAtrasados } from '../hooks/useAtrasados';

export default function AtrasadosPage() {
  const { data, isLoading, error } = useAtrasados('demo');

  if (isLoading) return <p>Cargando atrasados...</p>;
  if (error) return <p className="text-red-600">Error</p>;
  if (!data?.length) return <p className="text-green-600">Sin alumnos atrasados</p>;

  const total = data.length;
  const promedio = data.reduce((s, a) => s + a.dias_atraso, 0) / total;

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
            <th className="text-left p-2">Materia</th>
            <th className="text-left p-2">Pendientes</th>
            <th className="text-left p-2">Días atraso</th>
          </tr>
        </thead>
        <tbody>
          {data.map(a => (
            <tr key={a.id} className="border-t">
              <td className="p-2">{a.alumno_nombre}</td>
              <td className="p-2">{a.materia}</td>
              <td className="p-2">{a.entregas_pendientes}</td>
              <td className="p-2">{a.dias_atraso}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
