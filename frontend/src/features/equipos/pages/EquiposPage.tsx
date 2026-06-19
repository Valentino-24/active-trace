import { useQuery } from '@tanstack/react-query';
import api from '@/shared/services/api';
import { Spinner } from '@/shared/components/Spinner';
import { EmptyState } from '@/shared/components/EmptyState';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/Card';
import { AlertCircle, RefreshCw } from 'lucide-react';

export default function EquiposPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['mi-equipo'],
    queryFn: () => api.get('/equipos/mi-equipo').then(r => r.data),
  });

  if (isLoading) return <Spinner variant="full-page" size="lg" />;

  if (isError) {
    return (
      <div className="flex flex-col items-center gap-4 py-20 text-center">
        <AlertCircle className="h-12 w-12 text-red-500" />
        <div>
          <h2 className="text-xl font-semibold">Error al cargar equipos</h2>
          <p className="text-sm text-gray-500">{(error as Error)?.message || 'No se pudieron cargar los equipos'}</p>
        </div>
        <button onClick={() => refetch()} className="inline-flex items-center gap-2 px-4 py-2 rounded-md border hover:bg-gray-50 text-sm">
          <RefreshCw className="h-4 w-4" /> Reintentar
        </button>
      </div>
    );
  }

  if (!data?.total) {
    return <EmptyState title="No tenés equipos asignados" description="Cuando te asignen a una materia y cohorte, los vas a ver acá" />;
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Equipos Docentes</h1>
        <p className="text-sm text-gray-500">{data.total} asignaciones activas</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {data.items?.map((a: any) => (
          <Card key={a.id}>
            <CardHeader>
              <CardTitle className="text-base">{a.materia?.nombre || 'Sin materia'}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-500">Rol: {a.rol}</p>
              {a.cohorte && <p className="text-sm text-gray-500">Cohorte: {a.cohorte.nombre}</p>}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
