import * as NavigationMenu from '@radix-ui/react-navigation-menu';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { fetchHealth } from '../api/system';

import type { PropsWithChildren } from 'react';

const navItems = [
  { href: '/', label: 'Home' },
  { href: '/admin/ingest', label: 'Admin' },
  { href: '/states', label: 'States' },
  { href: '/bills', label: 'Bills' },
  { href: '/topics', label: 'Topics' },
  { href: '/search', label: 'Search' },
  { href: '/members', label: 'Members' },
];

export function AppShell({ children }: PropsWithChildren) {
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function checkHealth() {
      try {
        const health = await fetchHealth();
        if (!cancelled) {
          setApiHealthy(health.status === 'ok');
        }
      } catch {
        if (!cancelled) {
          setApiHealthy(false);
        }
      }
    }

    checkHealth();
    const timer = window.setInterval(checkHealth, 30000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">Congress Tracker</div>
        <div className={`health-pill ${apiHealthy ? 'health-pill-ok' : apiHealthy === false ? 'health-pill-down' : ''}`}>
          {apiHealthy === null ? 'Checking API...' : apiHealthy ? 'Ingest Online' : 'API Unreachable'}
        </div>
        <NavigationMenu.Root>
          <NavigationMenu.List className="nav-list">
            {navItems.map((item) => (
              <NavigationMenu.Item key={item.href}>
                <NavigationMenu.Link asChild>
                  <Link className="nav-link" to={item.href}>
                    {item.label}
                  </Link>
                </NavigationMenu.Link>
              </NavigationMenu.Item>
            ))}
          </NavigationMenu.List>
        </NavigationMenu.Root>
      </header>
      <main className="content">{children}</main>
    </div>
  );
}
