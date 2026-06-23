import { test, expect } from '@playwright/test'

test('market page loads', async ({ page }) => {
  await page.goto('/market')
  await expect(page.locator('h1, h2').filter({ hasText: /market|市场|行情/i }).first()).toBeVisible()
})

test('backtest page loads', async ({ page }) => {
  await page.goto('/backtest')
  await expect(page.locator('h1, h2').filter({ hasText: /backtest|回测/i }).first()).toBeVisible()
})

test('trading page loads', async ({ page }) => {
  await page.goto('/trading')
  await expect(page.locator('h1, h2').filter({ hasText: /trading|交易/i }).first()).toBeVisible()
})

test('strategy lab loads', async ({ page }) => {
  await page.goto('/strategy-lab')
  await expect(page.locator('h1, h2').filter({ hasText: /strategy|策略/i }).first()).toBeVisible()
})
