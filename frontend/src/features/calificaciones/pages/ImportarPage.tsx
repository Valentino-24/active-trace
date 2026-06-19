import { useState } from 'react';
import { useImportarCalificaciones } from '../hooks/useCalificaciones';

export default function ImportarPage() {
  const [file, setFile] = useState<File | null>(null);
  const mutation = useImportarCalificaciones();

  const handleUpload = () => {
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    mutation.mutate(fd);
  };

  return (
    <div>
      <h1 className="text-xl font-bold mb-4">Importar Calificaciones</h1>
      <div className="bg-white p-6 rounded shadow max-w-lg">
        <input type="file" accept=".csv,.xlsx" onChange={e => setFile(e.target.files?.[0] ?? null)}
          className="mb-4 block" />
        <button onClick={handleUpload} disabled={!file || mutation.isPending}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50">
          {mutation.isPending ? 'Importando...' : 'Importar'}
        </button>
        {mutation.isSuccess && <p className="text-green-600 mt-2">Importado correctamente</p>}
        {mutation.isError && <p className="text-red-600 mt-2">Error al importar</p>}
      </div>
    </div>
  );
}
