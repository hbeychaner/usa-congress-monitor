import { expect, test } from '@playwright/test';
import { ApiFixture } from './fixtures';

for (const target of ['/unexpected-fetch', 'http://127.0.0.1:8000/api/v1/not-a-fixture', 'https://example.invalid/not-a-fixture']) {
  test(`network guard blocks and reports ${target}`, async ({ context, page, baseURL }) => {
    if (!baseURL) throw new Error('Network guard test requires the configured preview origin.');
    const url = new URL(target, baseURL).href;
    const api = new ApiFixture(context, baseURL);
    await api.attach();
    await page.goto('/search');
    await expect(page.evaluate(target => fetch(target), url)).rejects.toThrow();
    expect(api.unexpectedRequests).toEqual([`GET ${url}`]);
    expect(() => api.verify()).toThrow('Unexpected API/external traffic');
  });
}
