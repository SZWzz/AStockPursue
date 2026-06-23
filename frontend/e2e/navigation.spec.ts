import { test, expect } from '@playwright/test'

test.describe('Navigation', () => {
  test('market page loads', async ({ page }) => {
    await page.goto('/market')
    await expect(page.locator('body')).toBeVisible()
  })

  test('backtest page loads', async ({ page }) => {
    await page.goto('/backtest')
    await expect(page.locator('body')).toBeVisible()
  })

  test('paper trading page loads', async ({ page }) => {
    await page.goto('/paper-trading')
    await expect(page.locator('body')).toBeVisible()
  })

  test('strategy lab page loads', async ({ page }) => {
    await page.goto('/strategy-lab')
    await expect(page.locator('body')).toBeVisible()
  })
})
