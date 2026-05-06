import { chromium } from 'playwright';

(async () => {
  console.log('Starting browser...');
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  console.log('Navigating to page...');
  try {
    await page.goto('https://mpbflndsk201-wsl.tabby-broadnose.ts.net:5174/jobs', { timeout: 30000, waitUntil: 'networkidle' });
    console.log('Page loaded. Title:', await page.title());
    await page.screenshot({ path: 'screenshot.png' });
    console.log('Screenshot saved.');
  } catch (err) {
    console.error('Error during navigation:', err);
  } finally {
    await browser.close();
  }
})();
