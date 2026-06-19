import { Link, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '@/shared/contexts/AuthContext';

const menuItems: Array<{ label: string; path: string; permission?: string }> = [
  { label: 'Dashboard', path: '/' },
  { label: 'Calificaciones', path: '/calificaciones', permission: 'calificaciones:importar' },
  { label: 'Atrasados', path: '/atrasados', permission: 'calificaciones:importar' },
  { label: 'Comunicaciones', path: '/comunicaciones', permission: 'comunicacion:enviar' },
  { label: 'Equipos', path: '/equipos', permission: 'equipos:gestionar' },
  { label: 'Encuentros', path: '/encuentros', permission: 'encuentros:gestionar' },
  { label: 'Avisos', path: '/avisos', permission: 'avisos:publicar' },
  { label: 'Tareas', path: '/tareas', permission: 'tareas:gestionar' },
  { label: 'Liquidaciones', path: '/liquidaciones', permission: 'liquidaciones:ver' },
  { label: 'Auditoría', path: '/auditoria', permission: 'auditoria:ver' },
];

export default function AppLayout() {
  const { user, logout, hasPermission } = useAuth();
  const navigate = useNavigate();

  const visibleItems = menuItems.filter((item) => !item.permission || hasPermission(item.permission));

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex h-screen">
      <aside className="w-64 bg-gray-900 text-white flex flex-col">
        <div className="p-4 border-b border-gray-700">
          <h2 className="text-lg font-bold">trace</h2>
          <p className="text-sm text-gray-400 truncate">{user?.email}</p>
        </div>
        <nav className="flex-1 p-2">
          {visibleItems.map((item) => (
            <Link key={item.path} to={item.path}
              className="block px-3 py-2 rounded hover:bg-gray-800 text-sm">
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="p-4 border-t border-gray-700">
          <button onClick={handleLogout}
            className="w-full text-left px-3 py-2 rounded hover:bg-gray-800 text-sm text-gray-400">
            Cerrar sesión
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-6 bg-gray-50">
        <Outlet />
      </main>
    </div>
  );
}
