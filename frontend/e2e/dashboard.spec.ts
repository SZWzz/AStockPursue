import { test, expect } from '@playwright/test'

test.describe('Dashboard page', () => {
  test('loads the dashboard layout', async ({ page }) => {
    await page.goto('/')

    // Body should be visible
    await expect(page.locator('body')).toBeVisible()

    // Page title should be set
    await expect(page).toHaveTitle(/AStockPursue/)
  })

  test('sidebar renders with navigation', async ({ page }) => {
    await page.goto('/')

    // Sidebar is an <aside> element
    const sidebar = page.locator('aside')
    await expect(sidebar).toBeVisible()

    // App name is displayed
    await expect(sidebar.getByText('AStockPursue')).toBeVisible()
  })
})
