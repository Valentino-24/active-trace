import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/shared/services/api';

export default function AvisosPage() {
  const queryClient = useQueryClient();
  const [titulo, setTitulo] = useState('');
  const [cuerpo, setCuerpo] = useState('');

  const { data } = useQuery({
    queryKey: ['avisos'],
    queryFn: () => api.get('/avisos').then(r => r.data),
  });

  const crear = useMutation({
    mutationFn: (body: any) => api.post('/avisos', body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['avisos'] }),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Avisos</h1>
      <div className="bg-white p-4 rounded shadow max-w-lg">
        <input value={titulo} onChange={e => setTitulo(e.target.value)} placeholder="Título"
          className="w-full border rounded p-2 mb-2" />
        <textarea value={cuerpo} onChange={e => setCuerpo(e.target.value)} placeholder="Cuerpo"
          className="w-full border rounded p-2 mb-3 h-24" />
        <button onClick={() => crear.mutate({ titulo, cuerpo, alcance: 'Global', severidad: 'Info', inicio_en: new Date().toISOString(), fin_en: new Date(Date.now() + 86400000 * 30).toISOString() })}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
          Publicar
        </button>
      </div>
      <div className="bg-white rounded shadow p-4">
        <p>Avisos publicados: {data?.total ?? 0}</p>
      </div>
    </div>
  );
}
