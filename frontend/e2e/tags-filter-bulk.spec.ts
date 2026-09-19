import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

async function register(page: Page, email: string, password: string) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm Password").fill(password);
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page).toHaveURL(/\/$/);
}

test("user can tag, filter, and bulk-complete a todo without exposing it to another user", async ({ browser }) => {
  const suffix = `${Date.now()}-${randomUUID().slice(0, 8)}`;
  const password = "Tier4Password123!";
  const tagName = `Project ${suffix}`;
  const todoTitle = `Tagged todo ${suffix}`;
  const contextA = await browser.newContext();
  const contextB = await browser.newContext();
  const pageA = await contextA.newPage();
  const pageB = await contextB.newPage();
  try {
    await register(pageA, `tier4-a-${suffix}@example.com`, password);
    await pageA.getByLabel("Tag name").fill(tagName);
    await pageA.getByRole("button", { name: "Add", exact: true }).click();
    await expect(pageA.getByLabel("Todo tag")).toContainText(tagName);

    await pageA.getByRole("button", { name: "Add Todo" }).click();
    const dialog = pageA.getByRole("dialog", { name: "Create Todo" });
    await dialog.getByLabel("Title").fill(todoTitle);
    await dialog.getByRole("button", { name: "Create" }).click();
    await expect(pageA.getByRole("checkbox", { name: todoTitle, exact: true })).toBeVisible();

    await pageA.getByLabel(`Attach tag to ${todoTitle}`).selectOption({ label: tagName });
    await expect(pageA.getByRole("checkbox", { name: todoTitle, exact: true }).locator("xpath=../..")).toContainText(tagName);
    await pageA.getByLabel("Todo tag").selectOption({ label: tagName });
    await expect(pageA.getByRole("checkbox", { name: todoTitle, exact: true })).toBeVisible();

    await pageA.getByLabel(`Select ${todoTitle}`).click();
    await pageA.getByRole("button", { name: "Mark completed" }).click();
    await expect(pageA.getByRole("checkbox", { name: todoTitle, exact: true })).toBeChecked();

    await register(pageB, `tier4-b-${suffix}@example.com`, password);
    await expect(pageB.getByText(todoTitle, { exact: true })).toHaveCount(0);
    await expect(pageB.getByText(tagName, { exact: true })).toHaveCount(0);
  } finally {
    await Promise.all([contextA.close(), contextB.close()]);
  }
});
