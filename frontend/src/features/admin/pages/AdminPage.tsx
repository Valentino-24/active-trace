import { useQuery } from '@tanstack/react-query';
import api from '@/shared/services/api';
import { Spinner } from '@/shared/components/Spinner';
import { EmptyState } from '@/shared/components/EmptyState';
import { AlertCircle, RefreshCw, ShieldCheck } from 'lucide-react';

export default function AdminPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['auditoria-recent'],
    queryFn: () => api.get('/auditoria/recientes?limit=20').then(r => r.data),
  });

  if (isLoading) return <Spinner variant="full-page" size="lg" />;
  if (isError) {
    return (
      <div className="flex flex-col items-center gap-4 py-20 text-center">
        <AlertCircle className="h-12 w-12 text-red-500" />
        <h2 className="text-xl font-semibold">Error al cargar auditoría</h2>
        <button onClick={() => refetch()} className="inline-flex items-center gap-2 px-4 py-2 rounded-md border hover:bg-gray-50 text-sm">
          <RefreshCw className="h-4 w-4" /> Reintentar
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Auditoría</h1>
        <p className="text-sm text-gray-500">{data?.total ?? 0} acciones registradas</p>
      </div>
      {!data?.items?.length ? (
        <EmptyState title="Sin registros de auditoría" description="Las acciones del sistema aparecerán acá" />
      ) : (
        <div className="bg-white rounded-lg border shadow-sm overflow-hidden">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left p-3 font-medium text-gray-600">Acción</th>
                <th className="text-left p-3 font-medium text-gray-600">Fecha</th>
                <th className="text-left p-3 font-medium text-gray-600">Filas</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((a: any, i: number) => (
                <tr key={i} className="border-t hover:bg-gray-50">
                  <td className="p-3 flex items-center gap-2">
                    <ShieldCheck className="h-3 w-3 text-green-500" /> {a.accion}
                  </td>
                  <td className="p-3 text-gray-500">{new Date(a.fecha_hora).toLocaleString()}</td>
                  <td className="p-3">{a.filas_afectadas}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
