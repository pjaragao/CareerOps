import { test, expect } from '@playwright/test';

test('Test clicks on Job Board and Manual Add', async ({ page }) => {
  await page.goto('http://localhost:5173/jobs');
  await page.waitForTimeout(2000);

  console.log('Testing Job Board Clicks...');
  
  // Try to click Add Manual Job
  const addBtn = page.getByText('Add Manual Job');
  await expect(addBtn).toBeVisible();
  await addBtn.click();
  console.log('Clicked Add Manual Job');
  
  await page.waitForTimeout(1000);
  const modalHeader = page.getByText('Add Manual Job', { exact: true }).nth(1); // The one in the modal
  if (await modalHeader.isVisible()) {
    console.log('SUCCESS: Add Manual Job modal is visible!');
  } else {
    console.log('FAILURE: Add Manual Job modal did NOT appear.');
  }

  await page.screenshot({ path: 'test_click_result.png' });
});
