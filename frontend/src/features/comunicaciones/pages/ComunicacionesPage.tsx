import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import api from '@/shared/services/api';

export default function ComunicacionesPage() {
  const [mensaje, setMensaje] = useState('');

  const { data: estados } = useQuery({
    queryKey: ['comunicaciones'],
    queryFn: () => api.get('/comunicaciones/lotes').then(r => r.data),
  });

  const enviar = useMutation({
    mutationFn: (body: { mensaje: string }) => api.post('/comunicaciones/enviar', body),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Comunicaciones</h1>
      <div className="bg-white p-4 rounded shadow max-w-lg">
        <textarea value={mensaje} onChange={e => setMensaje(e.target.value)}
          placeholder="Escribí el mensaje para alumnos atrasados..."
          className="w-full border rounded p-2 mb-3 h-24" />
        <button onClick={() => enviar.mutate({ mensaje })} disabled={!mensaje || enviar.isPending}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50">
          {enviar.isPending ? 'Enviando...' : 'Enviar'}
        </button>
        {enviar.isSuccess && <p className="text-green-600 mt-2">Mensaje enviado</p>}
      </div>
      <div>
        <h2 className="text-lg font-semibold mb-2">Estado de envíos</h2>
        {estados && (
          <table className="min-w-full bg-white rounded shadow">
            <thead className="bg-gray-100">
              <tr>
                <th className="text-left p-2">ID</th>
                <th className="text-left p-2">Estado</th>
              </tr>
            </thead>
            <tbody>
              {Array.isArray(estados) && estados.map((e: any, i: number) => (
                <tr key={i} className="border-t">
                  <td className="p-2">{e.id}</td>
                  <td className="p-2">{e.estado}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
