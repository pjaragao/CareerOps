import { test, expect } from '@playwright/test';

const pages = [
  { name: 'Dashboard', path: '/' },
  { name: 'Profile', path: '/profile' },
  { name: 'Strategies', path: '/strategies' },
  { name: 'Jobs', path: '/jobs' },
  { name: 'Kanban', path: '/kanban' },
  { name: 'Pipeline', path: '/pipeline' },
  { name: 'Interview', path: '/interview' },
  { name: 'Settings', path: '/settings' },
];

test.describe('App Comprehensive Audit', () => {
  for (const pageInfo of pages) {
    test(`Audit ${pageInfo.name} page`, async ({ page }) => {
      console.log(`Checking ${pageInfo.name}...`);
      
      // Capture console errors
      const errors: string[] = [];
      page.on('console', msg => {
        if (msg.type() === 'error') errors.push(msg.text());
      });

      await page.goto(`http://localhost:5173${pageInfo.path}`);
      await page.waitForTimeout(2000); // Wait for animations/data
      
      const screenshotPath = `audit_${pageInfo.name.toLowerCase()}.png`;
      await page.screenshot({ path: screenshotPath, fullPage: true });
      console.log(`Saved screenshot: ${screenshotPath}`);

      if (errors.length > 0) {
        console.error(`Errors found on ${pageInfo.name}:`, errors);
      }
    });
  }
});
