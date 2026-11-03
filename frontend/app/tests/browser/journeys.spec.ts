import type { Page, Route } from '@playwright/test';
import type * as Contracts from '../../src/shared/contracts/api';
import { bill, billId, bills, expect, memberId, test, unavailable } from './fixtures';

async function finishLateResponse(page: Page, route: Route, status: number): Promise<void> {
  const response = page.waitForResponse(route.request().url());
  await route.fulfill({ status, json: status === 200 ? bills(new URL(route.request().url())) : unavailable });
  await (await response).finished();
  // Let the completed fetch and React update reach a paint before checking isolation.
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
}

test('bill hydration unknown is explicit without hiding source records', async ({ page }) => {
  await page.goto(`/bills/${encodeURIComponent(billId)}`);
  await expect(page.getByRole('heading', { name: 'Fixture Health Bill', exact: true })).toBeVisible();
  await expect(page.getByRole('status', { name: 'Bill hydration' })).toContainText('Bill detail completeness unknown');
  await expect(page.getByRole('status', { name: 'Bill hydration' })).toContainText('Empty sections are not proof that no records exist.');
});

test('partial bill hydration is distinct from unknown', async ({ page, api }) => {
  api.override(`/api/v1/bills/${encodeURIComponent(billId)}`, route => route.fulfill({
    json: { bill: {
      ...bill, title: 'Partial source record',
      hydration: { schema_version: 1, source: 'congress.gov_api', status: 'partial',
        assessed_at: '2026-01-01T00:00:00Z', details: {
          relatedBills: { state: 'envelope', page_count: 1, expected_count: 2,
            fetched_count: 0, complete: false, reason: 'Unexpanded source envelope.' },
        },
        reason: 'Related bills remain an unresolved source envelope.' },
    } } satisfies Contracts.BillDetailResponse,
  }));
  await page.goto(`/bills/${encodeURIComponent(billId)}`);
  await expect(page.getByRole('heading', { name: 'Partial source record', exact: true })).toBeVisible();
  await expect(page.getByRole('status', { name: 'Bill hydration' })).toContainText('Partial bill details');
  await expect(page.getByRole('status', { name: 'Bill hydration' })).toContainText('Related bills remain an unresolved source envelope.');
});

test('complete bill hydration suppresses the warning without hiding source records', async ({ page, api }) => {
  const kinds: Contracts.BillDetailKind[] = [
    'actions', 'amendments', 'committees', 'cosponsors', 'relatedBills',
    'subjects', 'summaries', 'textVersions', 'titles',
  ];
  const details = Object.fromEntries(kinds.map(kind => [kind, {
    state: kind === 'subjects' ? 'object' : 'expanded', page_count: 1,
    expected_count: 0, fetched_count: 0, complete: true, reason: 'Verified empty response.',
  } satisfies Contracts.DetailEvidence]));
  api.override(`/api/v1/bills/${encodeURIComponent(billId)}`, route => route.fulfill({
    json: { bill: { ...bill, hydration: {
      schema_version: 1, source: 'congress.gov_api', status: 'complete',
      assessed_at: '2026-01-01T00:00:00Z', details, reason: 'All nine details retrieved.',
    } } } satisfies Contracts.BillDetailResponse,
  }));
  await page.goto(`/bills/${encodeURIComponent(billId)}`);
  await expect(page.getByRole('heading', { name: 'Fixture Health Bill', exact: true })).toBeVisible();
  await expect(page.getByRole('status', { name: 'Bill hydration' })).toHaveCount(0);
});

test('older servers without an assessment remain explicitly unknown', async ({ page, api }) => {
  const legacy = Object.fromEntries(Object.entries(bill).filter(([field]) => field !== 'hydration'));
  api.override(`/api/v1/bills/${encodeURIComponent(billId)}`, route => route.fulfill({ json: { bill: legacy } }));
  await page.goto(`/bills/${encodeURIComponent(billId)}`);
  await expect(page.getByRole('status', { name: 'Bill hydration' })).toContainText('The server supplied no hydration assessment.');
});

test('state -> member -> bill retains core records when optional analysis fails', async ({ page, api }) => {
  api.override(`/api/v1/bills/${encodeURIComponent(billId)}/similar`, route =>
    route.fulfill({ status: 503, json: unavailable }));
  await page.goto('/states/CA');
  await expect(page.getByRole('heading', { name: 'California (CA)', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Alex Fixture', exact: true }).click();
  await expect(page).toHaveURL(`/members/${memberId}`);
  await expect(page.getByRole('heading', { name: 'Alex Fixture', exact: true })).toBeVisible();
  await expect(page.getByText('Analysis has not been built and published yet.', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Fixture Health Bill', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: 'Fixture Health Bill', exact: true })).toBeVisible();
  await expect(page.getByText(unavailable.detail, { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Bill unavailable', exact: true })).toHaveCount(0);
});

test('member activity and topic outages do not hide member or bill records', async ({ page, api }) => {
  for (const path of [`/api/v1/members/${memberId}/topics`, `/api/v1/bills/${encodeURIComponent(billId)}/topics`]) {
    api.override(path, route => route.fulfill({ status: 503, json: unavailable }));
  }
  api.override(`/api/v1/members/${memberId}/activity`, route => route.fulfill({
    status: 503, json: { detail: 'Activity is incomplete; please retry.' } satisfies Contracts.ErrorResponse,
  }));
  await page.goto(`/members/${memberId}`);
  await expect(page.getByRole('heading', { name: 'Alex Fixture', exact: true })).toBeVisible();
  await expect(page.getByText(unavailable.detail, { exact: true })).toBeVisible();
  await expect(page.getByText('Unable to load activity: Activity is incomplete; please retry.', { exact: true })).toBeVisible();
  await page.goto(`/bills/${encodeURIComponent(billId)}`);
  await expect(page.getByRole('heading', { name: 'Fixture Health Bill', exact: true })).toBeVisible();
  await expect(page.getByText(`Bill topics: ${unavailable.detail}`, { exact: true })).toBeVisible();
});

for (const entity of ['bills', 'members']) {
  test(`${entity} outages are not empty or partial-success listings`, async ({ page, api }) => {
    api.override(`/api/v1/${entity === 'bills' ? 'bills/recent' : entity}`, route => route.fulfill({
      status: 503, json: { detail: 'Search is incomplete; please retry.' } satisfies Contracts.ErrorResponse,
    }));
    await page.goto(`/${entity}`);
    await expect(page.getByRole('alert')).toContainText('Search is incomplete; please retry.');
    await expect(page.getByRole('table')).toHaveCount(0);
    await expect(page.getByText(`No ${entity} match these filters.`, { exact: true })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Next', exact: true })).toBeDisabled();
  });
}

test('bill links restore filters, reload, keyboard paging, resets and history without duplicate retry entries', async ({ page, api }) => {
  await page.goto('/bills?query=health&congress=119&chamber=House&bill_type=hr&subject=Health&has_votes=true&page=2');
  const query = page.getByRole('textbox', { name: 'Search bills', exact: true });
  const votes = page.getByRole('checkbox', { name: 'Has votes', exact: true });
  await expect(page.getByText('Page 2 of 3', { exact: true })).toBeVisible();
  expect(Object.fromEntries(api.last('/api/v1/bills/recent').searchParams)).toEqual({
    query: 'health', congress: '119', chamber: 'House', bill_type: 'hr', subject: 'Health',
    has_votes: 'true', page: '2', limit: '50',
  });
  await expect(query).toHaveValue('health');
  await expect(page.getByRole('textbox', { name: 'Congress', exact: true })).toHaveValue('119');
  await expect(page.getByRole('textbox', { name: 'Subject', exact: true })).toHaveValue('Health');
  await expect(page.getByRole('combobox').nth(0)).toHaveText('House');
  await expect(page.getByRole('combobox').nth(1)).toHaveText('HR');
  await expect(votes).toBeChecked();
  await page.reload();
  await expect(query).toHaveValue('health');
  await page.getByRole('button', { name: 'Next', exact: true }).press('Enter');
  await expect(page.getByText('Page 3 of 3', { exact: true })).toBeVisible();
  expect(new URL(page.url()).searchParams.get('subject')).toBe('Health');
  expect(new URL(page.url()).searchParams.get('has_votes')).toBe('true');

  const beforeDraft = api.count('/api/v1/bills/recent');
  await query.fill('education');
  await votes.press('Space');
  expect(api.count('/api/v1/bills/recent')).toBe(beforeDraft);
  await query.press('Enter');
  await expect(page.getByText('education bill', { exact: true })).toBeVisible();
  await expect(page.getByText('Page 1 of 3', { exact: true })).toBeVisible();
  expect(new URL(page.url()).searchParams.has('has_votes')).toBe(false);
  const beforeRetry = api.count('/api/v1/bills/recent');
  await query.press('Enter');
  await expect.poll(() => api.count('/api/v1/bills/recent')).toBe(beforeRetry + 1);
  await expect(page.getByText('education bill', { exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByText('Page 3 of 3', { exact: true })).toBeVisible();
  await expect(query).toHaveValue('health');
  await expect(votes).toBeChecked();
  await page.goForward();
  await expect(query).toHaveValue('education');
  await expect(votes).not.toBeChecked();
});

test('member URLs retain historical parties and keyboard changes apply at page one', async ({ page, api }) => {
  await page.goto('/members?query=Alex&state=California&chamber=House&party=Whig&page=2');
  const party = page.getByRole('combobox').nth(1);
  await expect(page.getByText('Page 2 of 3', { exact: true })).toBeVisible();
  expect(Object.fromEntries(api.last('/api/v1/members').searchParams)).toEqual({
    query: 'Alex', state: 'California', chamber: 'House', party: 'Whig', page: '2', limit: '50',
  });
  await expect(page.getByRole('textbox', { name: 'Search', exact: true })).toHaveValue('Alex');
  await expect(page.getByRole('textbox', { name: 'State', exact: true })).toHaveValue('California');
  await expect(party).toHaveText('Whig');
  await page.reload();
  await expect(party).toHaveText('Whig');
  await page.getByRole('button', { name: 'Next', exact: true }).press('Enter');
  await expect(page.getByText('Page 3 of 3', { exact: true })).toBeVisible();
  const beforeDraft = api.count('/api/v1/members');
  await party.press('Space');
  await expect(page.getByRole('option', { name: 'Whig', exact: true })).toBeFocused();
  await page.keyboard.press('i');
  await expect(page.getByRole('option', { name: 'Independent', exact: true })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(party).toHaveText('Independent');
  expect(api.count('/api/v1/members')).toBe(beforeDraft);
  await page.getByRole('button', { name: 'Apply filters', exact: true }).press('Enter');
  await expect(page.getByText('Page 1 of 3', { exact: true })).toBeVisible();
  expect(new URL(page.url()).searchParams.get('party')).toBe('Independent');
  await page.goBack();
  await expect(page.getByText('Page 3 of 3', { exact: true })).toBeVisible();
  await expect(party).toHaveText('Whig');
});

test('search stays idle, restores a custom limit, groups results and distinguishes empty from unavailable', async ({ page, api }) => {
  api.override('/api/v1/search', async (route, url) => {
    if (url.searchParams.get('q') === 'broken') {
      await route.fulfill({ status: 503, json: { detail: 'Search is incomplete; please retry.' } satisfies Contracts.ErrorResponse });
    } else {
      await api.respond(route, url);
    }
  });
  await page.goto('/search');
  await expect(page.getByRole('heading', { name: 'Search', exact: true })).toBeVisible();
  await expect.poll(() => api.count('/ready')).toBe(1);
  expect(api.count('/api/v1/search')).toBe(0);
  await expect(page.getByRole('heading', { name: 'No Results', exact: true })).toHaveCount(0);
  await page.goto('/search?q=climate&types=bill,member&limit=37');
  const query = page.getByRole('textbox', { name: 'Search query', exact: true });
  await expect(query).toHaveValue('climate');
  await expect(page.getByRole('combobox')).toHaveText('37');
  await expect(page.getByRole('button', { name: 'state', exact: true })).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByRole('link', { name: 'climate bill', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'climate member', exact: true })).toBeVisible();
  const search = api.last('/api/v1/search').searchParams;
  expect(search.get('q')).toBe('climate');
  expect(search.get('limit')).toBe('37');
  expect(search.get('types')?.split(',').sort()).toEqual(['bill', 'member']);
  await page.reload();
  await expect(page.getByRole('combobox')).toHaveText('37');
  await page.getByRole('combobox').press('Space');
  await expect(page.getByRole('option', { name: '37', exact: true })).toBeFocused();
  await page.keyboard.press('End');
  await expect(page.getByRole('option', { name: '100', exact: true })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('combobox')).toHaveText('100');
  await page.getByRole('button', { name: 'state', exact: true }).press('Space');
  await query.press('Enter');
  await expect(page.getByRole('link', { name: 'climate state', exact: true })).toBeVisible();
  expect(new URL(page.url()).searchParams.get('limit')).toBe('100');
  await page.goBack();
  await expect(page.getByRole('combobox')).toHaveText('37');
  await expect(page.getByRole('button', { name: 'state', exact: true })).toHaveAttribute('aria-pressed', 'false');
  await page.goForward();
  await expect(page.getByRole('combobox')).toHaveText('100');
  await query.fill('empty');
  await query.press('Enter');
  await expect(page.getByRole('heading', { name: 'No Results', exact: true })).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await query.fill('broken');
  await query.press('Enter');
  await expect(page.getByRole('alert')).toContainText('Search is incomplete; please retry.');
  await expect(page.getByRole('heading', { name: 'No Results', exact: true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Search Summary', exact: true })).toHaveCount(0);
});

test('invalid URL states issue no data reads', async ({ page, api }) => {
  for (const path of ['/bills?page=0', '/members?chamber=Invalid', '/search?q=health&limit=101']) {
    await page.goto(path);
    await expect(page.getByRole('alert')).toBeVisible();
  }
  for (const path of ['/api/v1/bills/recent', '/api/v1/members', '/api/v1/search']) {
    expect(api.count(path)).toBe(0);
  }
});

test('server browsing bounds stop paging and rejected scopes never look empty', async ({ page, api }) => {
  api.override('/api/v1/bills/recent', async (route, url) => {
    if (url.searchParams.get('page') === '201') {
      await route.fulfill({ status: 422, json: {
        detail: [{ loc: ['query', 'page'], msg: 'Refine filters to browse beyond 10000 matches.', type: 'value_error' }],
      } satisfies Contracts.HTTPValidationError });
    } else {
      await api.respond(route, url);
    }
  });
  await page.goto('/bills?query=window&page=200');
  await expect(page.getByText('Page 200 of 200', { exact: true })).toBeVisible();
  await expect(page.getByText(/Browsing covers the first 10,000 matches/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Next', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Previous', exact: true }).press('Enter');
  await expect(page.getByText('Page 199 of 200', { exact: true })).toBeVisible();
  await page.goto('/bills?query=window&page=201');
  await expect(page.getByRole('alert')).toContainText('Refine filters');
  await expect(page.getByText('No bills match these filters.', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Next', exact: true })).toBeDisabled();
});

for (const status of [200, 503]) {
  test(`late ${status} response cannot overwrite the active bill query`, async ({ page, api }) => {
    const pending: Route[] = [];
    api.override('/api/v1/bills/recent', async (route, url) => {
      if (url.searchParams.get('query') === 'slow') pending.push(route);
      else await api.respond(route, url);
    });
    await page.goto('/bills?query=slow');
    await expect.poll(() => pending.length).toBe(1);
    await page.getByRole('textbox', { name: 'Search bills', exact: true }).fill('current');
    await page.getByRole('textbox', { name: 'Search bills', exact: true }).press('Enter');
    await expect(page.getByText('current bill', { exact: true })).toBeVisible();
    await finishLateResponse(page, pending[0], status);
    await expect(page.getByText('current bill', { exact: true })).toBeVisible();
    await expect(page.getByText('slow bill', { exact: true })).toHaveCount(0);
    await expect(page.getByRole('alert')).toHaveCount(0);
  });
}

test('navigation to idle search discards a pending result', async ({ page, api }) => {
  const pending: Route[] = [];
  api.override('/api/v1/search', async route => { pending.push(route); });
  await page.goto('/search?q=slow');
  await expect.poll(() => pending.length).toBe(1);
  await page.getByRole('link', { name: 'Search', exact: true }).click();
  await expect(page).toHaveURL('/search');
  const response = page.waitForResponse(pending[0].request().url());
  await api.respond(pending[0], new URL(pending[0].request().url()));
  await (await response).finished();
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await expect(page.getByRole('textbox', { name: 'Search query', exact: true })).toHaveValue('');
  await expect(page.getByRole('heading', { name: 'Search Summary', exact: true })).toHaveCount(0);
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('navigation and filters stay inside the viewport', async ({ page }) => {
  for (const path of ['/bills?query=health', '/members?party=Independent', '/search?q=health']) {
    await page.goto(path);
    await expect(page.getByRole('button', { name: /Apply filters|^Search$/ })).toBeVisible();
    const widths = await page.evaluate(() => ({
      document: document.documentElement.scrollWidth, viewport: window.innerWidth,
    }));
    expect(widths.document).toBeLessThanOrEqual(widths.viewport);
  }
});
