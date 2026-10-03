import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const url = process.env.FRONTEND_URL;
assert(url?.startsWith('https://'), 'FRONTEND_URL must be HTTPS');
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  // This check never signs in or performs inference.
  await page.route('**/api/chat', route => route.abort());
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const response = await page.goto(url, { waitUntil: 'networkidle' });
  assert.equal(response.status(), 200);
  await page.waitForFunction(() => document.querySelector('#root')?.textContent?.includes('Open Thread'));
  assert(!await page.getByText('Unable to start Open Thread.', { exact: true }).count(), 'Frontend configuration failed');
  assert.equal(errors.length, 0, 'Browser encountered an unhandled error');
  console.log('Unauthenticated Open Thread application loads in Chromium.');
} finally {
  await browser.close();
}
