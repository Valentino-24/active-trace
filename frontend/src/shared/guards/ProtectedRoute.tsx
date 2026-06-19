import { Navigate } from 'react-router-dom';
import { useAuth } from '@/shared/contexts/AuthContext';

interface Props {
  children: React.ReactNode;
  permission?: string;
}

export default function ProtectedRoute({ children, permission }: Props) {
  const { isAuthenticated, isLoading, hasPermission } = useAuth();

  if (isLoading) {
    return <div className="flex items-center justify-center h-screen">Cargando...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (permission && !hasPermission(permission)) {
    return <Navigate to="/403" replace />;
  }

  return <>{children}</>;
}
