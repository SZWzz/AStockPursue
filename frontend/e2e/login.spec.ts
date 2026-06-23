import { test, expect } from '@playwright/test'

test('login page renders', async ({ page }) => {
  await page.goto('/login')
  await expect(page.locator('input[name="username"]')).toBeVisible()
  await expect(page.locator('input[name="password"]')).toBeVisible()
  await expect(page.locator('button[type="submit"]')).toBeVisible()
})

test('empty login shows error', async ({ page }) => {
  await page.goto('/login')
  await page.locator('button[type="submit"]').click()
  await expect(page.locator('text=请输入用户名')).toBeVisible()
})

test('register link works', async ({ page }) => {
  await page.goto('/login')
  await page.locator('text=注册').click()
  await expect(page).toHaveURL(/register/)
})
