import { test, expect } from '@playwright/test';

test('capture dashboard screenshot', async ({ page }) => {
  await page.goto('http://localhost:5173');
  await page.waitForTimeout(2000); // Wait for animations
  await page.screenshot({ path: 'dashboard.png', fullPage: true });
  console.log('Screenshot saved as dashboard.png');
});
