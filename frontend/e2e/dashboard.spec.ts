import { test, expect } from '@playwright/test'

test('dashboard loads', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('aside')).toBeVisible()
})

test('sidebar has navigation links', async ({ page }) => {
  await page.goto('/')
  const sidebar = page.locator('aside')
  await expect(sidebar.locator('a[href="/"]')).toBeVisible()
  await expect(sidebar.locator('a[href="/market"]')).toBeVisible()
  await expect(sidebar.locator('a[href="/backtest"]')).toBeVisible()
  await expect(sidebar.locator('a[href="/trading"]')).toBeVisible()
  await expect(sidebar.locator('a[href="/strategy-lab"]')).toBeVisible()
})
