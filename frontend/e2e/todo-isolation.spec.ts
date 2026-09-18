import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

async function registerUser(page: Page, email: string, password: string) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm Password").fill(password);
  await page.getByRole("button", { name: "Create Account" }).click();

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Todo App" })).toBeVisible();
  await expect(page.getByText(email, { exact: true })).toBeVisible();
}

test("private todo is isolated between independent user sessions", async ({
  browser,
}) => {
  const runId = `${Date.now()}-${randomUUID().slice(0, 8)}`;
  const userAEmail = `isolation-a-${runId}@example.com`;
  const userBEmail = `isolation-b-${runId}@example.com`;
  const password = "IsolationPassword123!";
  const privateTodoTitle = `Private todo ${runId}`;
  const contextA = await browser.newContext();
  const contextB = await browser.newContext();
  const pageA = await contextA.newPage();
  const pageB = await contextB.newPage();

  try {
    await registerUser(pageA, userAEmail, password);
    await pageA.getByRole("button", { name: "Add Todo" }).click();
    const createDialog = pageA.getByRole("dialog", { name: "Create Todo" });
    await createDialog.getByLabel("Title").fill(privateTodoTitle);
    await createDialog.getByRole("button", { name: "Create" }).click();

    await expect(
      pageA.getByRole("checkbox", { name: privateTodoTitle }),
    ).toBeVisible();

    await registerUser(pageB, userBEmail, password);
    await expect(pageB.getByText("No todos yet", { exact: true })).toBeVisible();
    await expect(pageB.getByText(privateTodoTitle, { exact: true })).toHaveCount(0);

    await expect(pageA.getByText(userAEmail, { exact: true })).toBeVisible();
    await expect(
      pageA.getByRole("checkbox", { name: privateTodoTitle }),
    ).toBeVisible();

    const userAToken = await pageA.evaluate(() =>
      localStorage.getItem("access_token"),
    );
    const userBToken = await pageB.evaluate(() =>
      localStorage.getItem("access_token"),
    );
    expect(userAToken).toBeTruthy();
    expect(userBToken).toBeTruthy();
    expect(userAToken).not.toBe(userBToken);
  } finally {
    await Promise.all([contextA.close(), contextB.close()]);
  }
});
