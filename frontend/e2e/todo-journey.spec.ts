import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

test("registered user can create, complete, persist, and log out of a todo", async ({
  page,
}) => {
  const runId = `${Date.now()}-${randomUUID().slice(0, 8)}`;
  const email = `e2e-${runId}@example.com`;
  const password = "JourneyPassword123!";
  const todoTitle = `E2E todo ${runId}`;

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm Password").fill(password);
  await page.getByRole("button", { name: "Create Account" }).click();

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Todo App" })).toBeVisible();
  await expect(page.getByText(email)).toBeVisible();

  await page.getByRole("button", { name: "Add Todo" }).click();
  const createDialog = page.getByRole("dialog", { name: "Create Todo" });
  await createDialog.getByLabel("Title").fill(todoTitle);
  await createDialog.getByRole("button", { name: "Create" }).click();

  const todoCheckbox = page.getByRole("checkbox", { name: todoTitle });
  await expect(todoCheckbox).toBeVisible();
  await expect(todoCheckbox).not.toBeChecked();

  const updateResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "PUT" &&
      response.url().includes("/api/v1/todos/"),
  );
  await todoCheckbox.click();
  await expect(todoCheckbox).toBeChecked();
  const updateResponse = await updateResponsePromise;
  expect(updateResponse.ok()).toBe(true);

  await page.reload();
  await expect(page.getByRole("checkbox", { name: todoTitle })).toBeChecked();

  await page.getByRole("button", { name: "Logout" }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(
    page.getByRole("heading", { name: "Welcome Back" }),
  ).toBeVisible();
});
