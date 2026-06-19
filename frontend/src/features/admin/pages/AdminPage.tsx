import { useQuery } from '@tanstack/react-query';
import api from '@/shared/services/api';

export default function AdminPage() {
  const { data: auditoria } = useQuery({
    queryKey: ['auditoria-log'],
    queryFn: () => api.get('/auditoria/recientes?limit=10').then(r => r.data),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Administración</h1>
      <div className="bg-white p-4 rounded shadow">
        <h2 className="font-semibold mb-2">Auditoría Reciente</h2>
        <p>Últimas acciones: {auditoria?.total ?? 0}</p>
      </div>
    </div>
  );
}
