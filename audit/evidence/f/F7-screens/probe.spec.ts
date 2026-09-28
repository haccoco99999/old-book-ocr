import { test, expect } from '@playwright/test';
// Audit probe (scratch only): the NON-mock production build, served by `max preview` with its /api proxy,
// while the backend is unreachable. Does each screen render (shell + an error), not a blank page?
for (const path of ['/upload', '/queue', '/review', '/export', '/review/1', '/fonts']) {
  test(`renders ${path} with the backend down`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto(`http://127.0.0.1:18090${path}`);
    await page.waitForTimeout(2500);
    const text = (await page.locator('body').innerText()).replace(/\s+/g, ' ').slice(0, 400);
    console.log(`${path} :: ${text}`);
    console.log(`${path} :: pageerrors=${JSON.stringify(errors)}`);
    const menu = await page.getByRole('link', { name: /Giám sát|Monitoring/ }).count();
    console.log(`${path} :: monitoring links=${menu}`);
    await page.screenshot({ path: `audit-probe/shot${path.replace(/\//g, '_')}.png` });
    expect(text.length).toBeGreaterThan(20);
  });
}
