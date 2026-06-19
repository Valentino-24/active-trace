import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '@/shared/contexts/AuthContext';
import ProtectedRoute from '@/shared/guards/ProtectedRoute';
import AppLayout from '@/shared/components/AppLayout';
import ForbiddenPage from '@/shared/components/ForbiddenPage';
import LoginPage from '@/features/auth/pages/LoginPage';
import CalificacionesPage from '@/features/calificaciones/pages/CalificacionesPage';
import AtrasadosPage from '@/features/atrasados/pages/AtrasadosPage';
import ComunicacionesPage from '@/features/comunicaciones/pages/ComunicacionesPage';
import EquiposPage from '@/features/equipos/pages/EquiposPage';
import AvisosPage from '@/features/avisos/pages/AvisosPage';
import TareasPage from '@/features/tareas/pages/TareasPage';
import EncuentrosPage from '@/features/encuentros/pages/EncuentrosPage';
import ColoquiosPage from '@/features/coloquios/pages/ColoquiosPage';
import FinanzasPage from '@/features/finanzas/pages/FinanzasPage';
import AdminPage from '@/features/admin/pages/AdminPage';

const queryClient = new QueryClient();

function Dashboard() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Dashboard</h1>
      <p className="text-gray-600">Bienvenido a activia-trace.</p>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/403" element={<ForbiddenPage />} />
            <Route path="/" element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }>
              <Route index element={<Dashboard />} />
              {/* Placeholder routes — features added in C-22/23/24 */}
              <Route path="calificaciones" element={<ProtectedRoute permission="calificaciones:importar"><CalificacionesPage /></ProtectedRoute>} />
              <Route path="atrasados" element={<ProtectedRoute permission="calificaciones:importar"><AtrasadosPage /></ProtectedRoute>} />
              <Route path="comunicaciones" element={<ProtectedRoute permission="comunicacion:enviar"><ComunicacionesPage /></ProtectedRoute>} />
              <Route path="equipos" element={<ProtectedRoute permission="equipos:gestionar"><EquiposPage /></ProtectedRoute>} />
              <Route path="encuentros" element={<ProtectedRoute permission="encuentros:gestionar"><EncuentrosPage /></ProtectedRoute>} />
              <Route path="avisos" element={<ProtectedRoute permission="avisos:publicar"><AvisosPage /></ProtectedRoute>} />
              <Route path="tareas" element={<ProtectedRoute permission="tareas:gestionar"><TareasPage /></ProtectedRoute>} />
              <Route path="coloquios" element={<ProtectedRoute><ColoquiosPage /></ProtectedRoute>} />
              <Route path="liquidaciones" element={<ProtectedRoute permission="liquidaciones:ver"><FinanzasPage /></ProtectedRoute>} />
              <Route path="auditoria" element={<ProtectedRoute permission="auditoria:ver"><AdminPage /></ProtectedRoute>} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
