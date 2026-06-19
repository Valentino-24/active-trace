import { useQuery } from '@tanstack/react-query';
import api from '@/shared/services/api';
import { Spinner } from '@/shared/components/Spinner';
import { EmptyState } from '@/shared/components/EmptyState';
import { AlertCircle, RefreshCw, TrendingUp, Clock } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/Card';

export default function AtrasadosPage() {
  const { data: equipos } = useQuery({ queryKey: ['mi-equipo'], queryFn: () => api.get('/equipos/mi-equipo').then(r => r.data) });
  const materiaId = equipos?.items?.[0]?.materia?.id;
  const cohorteId = equipos?.items?.[0]?.cohorte?.id;

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['atrasados', materiaId, cohorteId],
    queryFn: () => api.get('/analisis/atrasados', { params: { materia_id: materiaId, cohorte_id: cohorteId } }).then(r => r.data),
    enabled: !!materiaId && !!cohorteId,
  });

  if (!materiaId) return <EmptyState title="Sin materia asignada" description="Necesitás una asignación activa para ver atrasados" />;
  if (isLoading) return <Spinner variant="full-page" size="lg" />;
  if (isError) return <div className="flex flex-col items-center gap-4 py-20"><AlertCircle className="h-12 w-12 text-red-500" /><p className="text-red-600">{(error as Error)?.message || 'Error al cargar'}</p></div>;

  const items = data?.items || [];

  if (!items.length) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Alumnos Atrasados</h1>
        <EmptyState title="Sin alumnos atrasados" description="No hay entregas pendientes en tu materia" />
      </div>
    );
  }

  const promedio = items.reduce((s: number, a: any) => s + (a.dias_atraso || 0), 0) / items.length;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Alumnos Atrasados</h1>
      <div className="grid gap-4 md:grid-cols-2">
        <Card><CardHeader className="flex flex-row items-center justify-between pb-2"><CardTitle>Total</CardTitle><AlertCircle className="h-4 w-4 text-red-500" /></CardHeader><CardContent><p className="text-2xl font-bold">{items.length}</p></CardContent></Card>
        <Card><CardHeader className="flex flex-row items-center justify-between pb-2"><CardTitle>Promedio días</CardTitle><Clock className="h-4 w-4 text-amber-500" /></CardHeader><CardContent><p className="text-2xl font-bold">{promedio.toFixed(1)}</p></CardContent></Card>
      </div>
      <div className="bg-white rounded-lg border shadow-sm overflow-hidden">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 border-b"><tr><th className="text-left p-3">Alumno</th><th className="text-left p-3">Pendientes</th><th className="text-left p-3">Días atraso</th></tr></thead>
          <tbody>{items.map((a: any) => <tr key={a.id || a.alumno_id} className="border-t hover:bg-gray-50"><td className="p-3">{a.alumno_nombre || a.alumno_id}</td><td className="p-3">{a.entregas_pendientes}</td><td className="p-3">{a.dias_atraso}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}
