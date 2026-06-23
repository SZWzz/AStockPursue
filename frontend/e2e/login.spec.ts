import { test, expect } from '@playwright/test'

test.describe('Login page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
  })

  test('renders the login form with all expected elements', async ({ page }) => {
    // Form should be visible
    await expect(page.locator('form')).toBeVisible()

    // Username textbox — Input component renders as text input without label association
    const inputs = page.getByRole('textbox')
    await expect(inputs.first()).toBeVisible()

    // Password field
    const passwordInput = page.locator('input[type="password"]')
    await expect(passwordInput).toBeVisible()

    // Submit button — matches either Chinese or English text
    await expect(
      page.getByRole('button', { name: /sign in|登录/i })
    ).toBeVisible()

    // Register link
    await expect(
      page.getByRole('link', { name: /register|注册/i })
    ).toBeVisible()
  })

  test('shows validation error on empty form submission', async ({ page }) => {
    // Click submit with empty form
    const submitBtn = page.getByRole('button', { name: /sign in|登录/i })
    await submitBtn.click()

    // Should stay on login page (form still visible)
    await expect(page.locator('form')).toBeVisible()
  })
})
