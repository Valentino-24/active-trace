import { useQuery } from '@tanstack/react-query';
import api from '@/shared/services/api';

export default function FinanzasPage() {
  const { data: liquidaciones } = useQuery({
    queryKey: ['liquidaciones'],
    queryFn: () => api.get('/liquidaciones/historial').then(r => r.data),
  });

  const { data: salarios } = useQuery({
    queryKey: ['salarios-base'],
    queryFn: () => api.get('/salarios/base').then(r => r.data),
  });

  const { data: facturas } = useQuery({
    queryKey: ['facturas'],
    queryFn: () => api.get('/facturas').then(r => r.data),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Finanzas</h1>

      <div className="bg-white p-4 rounded shadow">
        <h2 className="font-semibold mb-2">Liquidaciones</h2>
        <p>Historial: {liquidaciones?.total ?? 0} registros</p>
      </div>

      <div className="bg-white p-4 rounded shadow">
        <h2 className="font-semibold mb-2">Grilla Salarial</h2>
        <p>Salarios base: {salarios?.length ?? 0} configurados</p>
      </div>

      <div className="bg-white p-4 rounded shadow">
        <h2 className="font-semibold mb-2">Facturas</h2>
        <p>Facturas registradas: {facturas?.length ?? 0}</p>
      </div>
    </div>
  );
}
