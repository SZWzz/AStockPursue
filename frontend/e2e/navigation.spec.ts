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
    // Next.js dev mode may compile on first access; wait for page to fully load
    await page.waitForLoadState('load')
    // Strategy lab uses SidebarLayout which renders two <main> elements;
    // use the sidebar layout's <main> (no id, inside the layout)
    await expect(page.getByRole('main').last()).toBeVisible()
  })
})
