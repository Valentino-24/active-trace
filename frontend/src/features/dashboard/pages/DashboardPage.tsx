import { useAuth } from '@/shared/contexts/AuthContext';
import { useQuery } from '@tanstack/react-query';
import api from '@/shared/services/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/Card';
import { CalendarDays, Bell, MessageSquare, Users, GraduationCap, ShieldCheck } from 'lucide-react';

export default function DashboardPage() {
  const { user } = useAuth();

  const { data: equipos } = useQuery({ queryKey: ['mi-equipo'], queryFn: () => api.get('/equipos/mi-equipo').then(r => r.data) });
  const { data: auditoria } = useQuery({ queryKey: ['auditoria-recent'], queryFn: () => api.get('/auditoria/recientes?limit=5').then(r => r.data) });
  const { data: avisos } = useQuery({ queryKey: ['avisos'], queryFn: () => api.get('/avisos').then(r => r.data) });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Bienvenido, {user?.display_name || user?.email}</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle>Equipos</CardTitle>
            <div className="rounded-lg bg-blue-50 p-2"><Users className="h-4 w-4 text-blue-600" /></div>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{equipos?.total ?? 0}</p>
            <CardDescription>Asignaciones activas</CardDescription>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle>Avisos</CardTitle>
            <div className="rounded-lg bg-amber-50 p-2"><Bell className="h-4 w-4 text-amber-600" /></div>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{avisos?.total ?? 0}</p>
            <CardDescription>Publicados</CardDescription>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle>Auditoría</CardTitle>
            <div className="rounded-lg bg-green-50 p-2"><ShieldCheck className="h-4 w-4 text-green-600" /></div>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{auditoria?.total ?? 0}</p>
            <CardDescription>Últimas acciones</CardDescription>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Resumen rápido</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-blue-50 p-2"><Users className="h-4 w-4 text-blue-600" /></div>
              <div><p className="text-sm font-medium">Docentes activos</p><p className="text-xs text-gray-500">Este cuatrimestre</p></div>
            </div>
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-purple-50 p-2"><GraduationCap className="h-4 w-4 text-purple-600" /></div>
              <div><p className="text-sm font-medium">Comisiones activas</p><p className="text-xs text-gray-500">Período actual</p></div>
            </div>
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-amber-50 p-2"><CalendarDays className="h-4 w-4 text-amber-600" /></div>
              <div><p className="text-sm font-medium">Próximos encuentros</p><p className="text-xs text-gray-500">Sin encuentros programados</p></div>
            </div>
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-green-50 p-2"><MessageSquare className="h-4 w-4 text-green-600" /></div>
              <div><p className="text-sm font-medium">Comunicaciones</p><p className="text-xs text-gray-500">Sin pendientes</p></div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Actividad reciente</CardTitle></CardHeader>
          <CardContent>
            {auditoria?.items?.length ? (
              <ul className="space-y-2">
                {auditoria.items.slice(0, 5).map((a: any, i: number) => (
                  <li key={i} className="text-sm flex justify-between">
                    <span>{a.accion}</span>
                    <span className="text-gray-400 text-xs">{new Date(a.fecha_hora).toLocaleDateString()}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="py-8 text-center text-sm text-gray-400">Sin actividad reciente para mostrar</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
