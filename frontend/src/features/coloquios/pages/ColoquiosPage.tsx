import { useQuery } from '@tanstack/react-query';
import api from '@/shared/services/api';

export default function ColoquiosPage() {
  const { data } = useQuery({
    queryKey: ['coloquios'],
    queryFn: () => api.get('/coloquios').then(r => r.data),
  });

  return (
    <div>
      <h1 className="text-xl font-bold mb-4">Coloquios</h1>
      <div className="bg-white rounded shadow p-4">
        <p>Coloquios registrados: {data?.total ?? 0}</p>
      </div>
    </div>
  );
}
