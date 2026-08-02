import { chromium } from 'playwright';

const browser = await chromium.launch();

async function shot(name, url, waitFor) {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });

  await page.addInitScript(() => {
    sessionStorage.setItem('staff_authed', 'true');
  });

  await page.goto(url, { waitUntil: 'domcontentloaded' });

  // Wait for an element that only exists after auth passes
  if (waitFor) {
    await page.waitForSelector(waitFor, { timeout: 8000 });
  }
  await page.waitForTimeout(400);

  await page.screenshot({
    path: `/Users/samarthhiremath/work/Rosewood_Hackathon/${name}.png`,
    fullPage: false
  });
  console.log(`Saved ${name}.png`);
  await ctx.close();
}

// 'h1' with text "Concierge Tablet" or "Morning Arrivals" only renders post-auth
await shot('ui_concierge', 'http://localhost:3001/concierge', 'text=Concierge Tablet');
await shot('ui_manager',   'http://localhost:3001/manager',   'text=Morning Arrivals');
await browser.close();
