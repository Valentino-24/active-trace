import { useQuery } from '@tanstack/react-query';
import api from '@/shared/services/api';
import { Spinner } from '@/shared/components/Spinner';
import { EmptyState } from '@/shared/components/EmptyState';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/Card';
import { Bell, AlertCircle, RefreshCw } from 'lucide-react';

export default function AvisosPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['avisos'],
    queryFn: () => api.get('/avisos').then(r => r.data),
  });

  if (isLoading) return <Spinner variant="full-page" size="lg" />;

  if (isError) {
    return (
      <div className="flex flex-col items-center gap-4 py-20 text-center">
        <AlertCircle className="h-12 w-12 text-red-500" />
        <h2 className="text-xl font-semibold">Error al cargar avisos</h2>
        <p className="text-sm text-gray-500">{(error as Error)?.message || 'No se pudieron cargar'}</p>
        <button onClick={() => refetch()} className="inline-flex items-center gap-2 px-4 py-2 rounded-md border hover:bg-gray-50 text-sm">
          <RefreshCw className="h-4 w-4" /> Reintentar
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Avisos</h1>
        <p className="text-sm text-gray-500">{data?.total ?? 0} publicados</p>
      </div>
      {!data?.items?.length ? (
        <EmptyState title="No hay avisos publicados" description="Los avisos institucionales aparecerán acá" />
      ) : (
        <div className="space-y-3">
          {data.items.map((a: any) => (
            <Card key={a.id}>
              <CardHeader className="flex flex-row items-start justify-between">
                <div>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Bell className="h-4 w-4 text-amber-500" /> {a.titulo}
                  </CardTitle>
                  <p className="text-sm text-gray-500 mt-1">{a.cuerpo}</p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full ${a.activo ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                  {a.activo ? 'Activo' : 'Inactivo'}
                </span>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
