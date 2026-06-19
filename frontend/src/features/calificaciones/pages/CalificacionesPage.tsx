import TablaNotas from '../components/TablaNotas';
import ImportarPage from './ImportarPage';

export default function CalificacionesPage() {
  return (
    <div className="space-y-6">
      <ImportarPage />
      <TablaNotas />
    </div>
  );
}
