import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/shared/services/api';

export default function TareasPage() {
  const queryClient = useQueryClient();
  const [descripcion, setDescripcion] = useState('');

  const { data } = useQuery({
    queryKey: ['tareas'],
    queryFn: () => api.get('/tareas').then(r => r.data),
  });

  const crear = useMutation({
    mutationFn: (body: any) => api.post('/tareas', body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tareas'] }),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Tareas Internas</h1>
      <div className="bg-white p-4 rounded shadow max-w-lg">
        <textarea value={descripcion} onChange={e => setDescripcion(e.target.value)}
          placeholder="Descripción de la tarea..."
          className="w-full border rounded p-2 mb-3 h-24" />
        <button onClick={() => crear.mutate({ descripcion, asignado_a: 'placeholder' })}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
          Crear tarea
        </button>
      </div>
      <div className="bg-white rounded shadow p-4">
        <p>Tareas: {data?.total ?? 0}</p>
      </div>
    </div>
  );
}
