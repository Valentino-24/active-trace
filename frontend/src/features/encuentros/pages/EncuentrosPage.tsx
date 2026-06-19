import { useQuery } from '@tanstack/react-query';
import api from '@/shared/services/api';

export default function EncuentrosPage() {
  const { data } = useQuery({
    queryKey: ['encuentros'],
    queryFn: () => api.get('/encuentros').then(r => r.data),
  });

  return (
    <div>
      <h1 className="text-xl font-bold mb-4">Encuentros</h1>
      <div className="bg-white rounded shadow p-4">
        <p>Encuentros programados: {data?.total ?? 0}</p>
      </div>
    </div>
  );
}
