import { Badge, Box, Flex, Heading, Link as RadixLink } from '@radix-ui/themes';
import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

import { fetchReadiness } from '../api/system';

import type { PropsWithChildren } from 'react';

const navItems = [
  { href: '/', label: 'Home' },
  { href: '/admin/ingest', label: 'Admin' },
  { href: '/states', label: 'States' },
  { href: '/bills', label: 'Bills' },
  { href: '/topics', label: 'Topics' },
  { href: '/parties', label: 'Parties' },
  { href: '/search', label: 'Search' },
  { href: '/members', label: 'Members' },
  { href: '/graph', label: 'Graph' },
];

export function AppShell({ children }: PropsWithChildren) {
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);
  const location = useLocation();

  useEffect(() => {
    let cancelled = false;

    async function checkHealth() {
      try {
        const health = await fetchReadiness();
        if (!cancelled) {
          setApiHealthy(health.status === 'ready');
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

  const healthLabel = apiHealthy === null ? 'Checking API...' : apiHealthy ? 'API Ready' : 'API Not Ready';
  const healthColor = apiHealthy === null ? 'gray' : apiHealthy ? 'green' : 'red';

  return (
    <Box className="app-shell">
      <Flex asChild justify="between" align="center" wrap="wrap" gap="4" px="5" py="3" className="topbar">
        <header>
          <Heading as="h1" size="4" className="brand">
            Congress Tracker
          </Heading>
          <Badge color={healthColor} variant="soft" radius="full" size="2">
            {healthLabel}
          </Badge>
          <Flex asChild gap="4" align="center" wrap="wrap">
            <nav aria-label="Primary">
              {navItems.map((item) => {
                const active = location.pathname === item.href;
                return (
                  <RadixLink
                    key={item.href}
                    asChild
                    weight={active ? 'bold' : 'medium'}
                    color={active ? 'teal' : 'gray'}
                    highContrast={active}
                  >
                    <Link to={item.href}>{item.label}</Link>
                  </RadixLink>
                );
              })}
            </nav>
          </Flex>
        </header>
      </Flex>
      <Box asChild className="content">
        <main>{children}</main>
      </Box>
    </Box>
  );
}
