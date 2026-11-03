import { expect, test } from '@playwright/test';
import type { NeighborhoodResponse } from '../../src/shared/contracts/api';

const member = process.env.GRAPH_VOTING_ACCEPTANCE_MEMBER;
const version = process.env.GRAPH_VOTING_ACCEPTANCE_VERSION;

test('real Congress 114 voting edges render with verified publication identity', async ({ page }, testInfo) => {
  test.skip(!member || !version, 'Requires an explicitly selected staged/serving graph API and member/version.');
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.goto(`/graph?member=${encodeURIComponent(member!)}`);
  await expect(page.getByRole('heading', { name: 'Member graph', exact: true })).toBeVisible();
  await page.getByRole('combobox').nth(0).click();
  const responsePromise = page.waitForResponse(response => {
    const url = new URL(response.url());
    return url.pathname === '/api/v1/graph/neighborhood' && url.searchParams.get('congress') === '114';
  });
  await page.getByRole('option', { name: '114th', exact: true }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const graph: NeighborhoodResponse = await response.json();
  expect(graph.congress).toBe(114);
  expect(graph.versions.voting).toBe(version);
  expect(graph.analysis.voting?.state).toBe('available');
  expect(graph.nodes.some(node => node.member.bioguide_id === member && node.is_seed)).toBe(true);
  expect(graph.links.length).toBeGreaterThan(0);
  expect(graph.links.some(link => (link.signal_scores.voting ?? 0) > 0)).toBe(true);
  for (const link of graph.links) {
    expect(Number.isFinite(link.score) && link.score >= 0 && link.score <= 1).toBe(true);
    for (const score of Object.values(link.signal_scores)) {
      expect(Number.isFinite(score) && score >= 0 && score <= 1).toBe(true);
    }
  }
  await expect(page.locator('canvas').first()).toBeVisible();
  expect(errors).toEqual([]);
  await testInfo.attach('neighborhood.json', { body: JSON.stringify(graph), contentType: 'application/json' });
  await page.screenshot({ path: testInfo.outputPath('voting-114.png'), fullPage: true });
});
