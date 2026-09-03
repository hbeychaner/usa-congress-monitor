import { AppShell } from './components/AppShell';
import { AppRoutes } from './routing/routes';

export default function App() {
  return (
    <AppShell>
      <AppRoutes />
    </AppShell>
  );
}
