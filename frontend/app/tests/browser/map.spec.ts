import type { FeatureCollection, Polygon } from 'geojson';
import { expect, test } from './fixtures';

test('the map renders a fixture state and navigates to its delegation', async ({ context, page }) => {
  const geography: FeatureCollection<Polygon> = {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature', id: '06', properties: { name: 'Synthetic California' },
      geometry: {
        type: 'Polygon',
        coordinates: [[[-124, 32], [-124, 42], [-114, 42], [-114, 32], [-124, 32]]],
      },
    }],
  };
  await context.route('https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json',
    route => route.fulfill({ json: geography }));
  await page.goto('/states');
  const state = page.locator('path.map-state[aria-label="California"]');
  await expect(state).toBeVisible();
  await expect(state).toHaveAttribute('d', /^M.+Z$/);
  await state.focus();
  await expect(page.getByRole('heading', { name: 'California (CA)', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Open state timeline', exact: true }).press('Enter');
  await expect(page).toHaveURL('/states/CA');
  await expect(page.getByRole('link', { name: 'Alex Fixture', exact: true })).toBeVisible();
});
