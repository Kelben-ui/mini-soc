// Capture dashboard screenshots for the analyst user guide.
//
// Prerequisite: a running stack (backend + dashboard) with demo data —
// see seed_demo.py and README.md in this directory.
//
//   cd docs/testing/screenshots
//   npm install
//   npx playwright install chromium
//   npm run capture
//
// Environment:
//   MINI_SOC_URL    dashboard base URL    (default http://127.0.0.1:5173)
//   MINI_SOC_USER   login username        (default admin)
//   MINI_SOC_PASS   login password        (default demo-password-123)
//   MINI_SOC_SHOTS  output directory      (default ../../images/screenshots)
//
// The script logs in through the real form, then visits each route and saves a
// screenshot. A route that fails to render is logged and skipped, never fatal.
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from 'playwright';

const here = dirname(fileURLToPath(import.meta.url));
const BASE_URL = process.env.MINI_SOC_URL || 'http://127.0.0.1:5173';
const USERNAME = process.env.MINI_SOC_USER || 'admin';
const PASSWORD = process.env.MINI_SOC_PASS || 'demo-password-123';
const OUT = process.env.MINI_SOC_SHOTS
  ? resolve(process.env.MINI_SOC_SHOTS)
  : resolve(here, '../../images/screenshots');

mkdirSync(OUT, { recursive: true });

let browser;
let page;

async function settle() {
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(500);
}

async function shot(name, { fullPage = false } = {}) {
  await settle();
  await page.screenshot({ path: resolve(OUT, name), fullPage });
  console.log(`captured ${name}`);
}

async function api(path) {
  return page.evaluate(async (p) => {
    const res = await fetch(p, {
      headers: { Authorization: `Bearer ${localStorage.getItem('jwt')}` },
    });
    if (!res.ok) return null;
    try {
      return await res.json();
    } catch {
      return null;
    }
  }, path);
}

function firstId(data, key) {
  const items = Array.isArray(data) ? data : data?.items;
  if (!Array.isArray(items) || items.length === 0) return null;
  return items[0][key] ?? null;
}

// Prefer a Playwright-managed browser, but fall back to an installed Chrome or
// Edge. This lets the capture run on machines that already have a browser even
// when `playwright install` is unavailable (e.g. a full disk). Override with
// MINI_SOC_CHANNEL=chrome|msedge.
async function launchBrowser() {
  const forced = process.env.MINI_SOC_CHANNEL;
  const attempts = forced
    ? [{ channel: forced }]
    : [{}, { channel: 'chrome' }, { channel: 'msedge' }];
  let lastError;
  for (const options of attempts) {
    try {
      const browser = await chromium.launch(options);
      console.log(`launched browser${options.channel ? ` (channel: ${options.channel})` : ''}`);
      return browser;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

async function main() {
  browser = await launchBrowser();
  page = await browser.newPage({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });

  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
  await shot('00-login.png');

  await page.getByPlaceholder('Username').fill(USERNAME);
  await page.getByPlaceholder('Password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Log in' }).click();
  await page.waitForTimeout(900);
  await shot('01-overview.png');

  const alertId = firstId(await api('/api/alerts?limit=1'), 'alert_id');
  const incidentId = firstId(await api('/api/incidents'), 'incident_id');
  const chainId = firstId(await api('/api/chains'), 'chain_id');

  const pages = [
    ['02-alerts.png', '/alerts', false],
    [alertId && '03-alert-detail.png', `/alerts/${alertId}`, true],
    ['04-chains.png', '/chains', false],
    [chainId && '05-chain-detail.png', `/chains/${chainId}`, true],
    ['06-incidents.png', '/incidents', false],
    [incidentId && '07-incident-detail.png', `/incidents/${incidentId}`, true],
    ['08-events.png', '/events', false],
    ['09-rules.png', '/rules', false],
    ['10-reports.png', '/reports', false],
    ['11-users.png', '/users', false],
  ];

  for (const [name, route, fullPage] of pages) {
    if (!name) continue;
    try {
      await page.goto(`${BASE_URL}${route}`, { waitUntil: 'domcontentloaded' });
      await shot(name, { fullPage });
    } catch (error) {
      console.warn(`skipped ${name}: ${error.message}`);
    }
  }
}

try {
  await main();
  console.log(`\nScreenshots written to ${OUT}`);
} catch (error) {
  console.error(error);
  process.exitCode = 1;
} finally {
  await browser?.close();
}
