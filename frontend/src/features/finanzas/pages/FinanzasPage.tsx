import { useQuery } from '@tanstack/react-query';
import api from '@/shared/services/api';
import { Spinner } from '@/shared/components/Spinner';
import { EmptyState } from '@/shared/components/EmptyState';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/Card';
import { DollarSign, FileText, Receipt } from 'lucide-react';

export default function FinanzasPage() {
  const { data: liquidaciones, isLoading: l1 } = useQuery({ queryKey: ['liquidaciones'], queryFn: () => api.get('/liquidaciones/historial').then(r => r.data) });
  const { data: salarios, isLoading: l2 } = useQuery({ queryKey: ['salarios-base'], queryFn: () => api.get('/salarios/base').then(r => r.data) });
  const { data: facturas, isLoading: l3 } = useQuery({ queryKey: ['facturas'], queryFn: () => api.get('/facturas').then(r => r.data) });

  if (l1 || l2 || l3) return <Spinner variant="full-page" size="lg" />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Finanzas</h1>
      <div className="grid gap-4 md:grid-cols-3">
        <Card><CardHeader className="flex flex-row items-center justify-between pb-2"><CardTitle>Liquidaciones</CardTitle><DollarSign className="h-4 w-4 text-green-600" /></CardHeader><CardContent><p className="text-2xl font-bold">{liquidaciones?.total ?? 0}</p><p className="text-xs text-gray-500">Historial</p></CardContent></Card>
        <Card><CardHeader className="flex flex-row items-center justify-between pb-2"><CardTitle>Salarios Base</CardTitle><FileText className="h-4 w-4 text-blue-600" /></CardHeader><CardContent><p className="text-2xl font-bold">{salarios?.length ?? 0}</p><p className="text-xs text-gray-500">Configurados</p></CardContent></Card>
        <Card><CardHeader className="flex flex-row items-center justify-between pb-2"><CardTitle>Facturas</CardTitle><Receipt className="h-4 w-4 text-purple-600" /></CardHeader><CardContent><p className="text-2xl font-bold">{facturas?.length ?? 0}</p><p className="text-xs text-gray-500">Registradas</p></CardContent></Card>
      </div>
    </div>
  );
}
