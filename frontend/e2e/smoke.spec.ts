import { expect, test } from "@playwright/test";

const nav = (page: import("@playwright/test").Page, name: string) =>
  page.getByRole("navigation", { name: "Main" }).getByRole("link", { name });

test("index, ask with citations, inspect source and debug, follow-up, evaluate", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Index", exact: true }).click();
  await expect(page.getByText(/[1-9]\d* chunks/)).toBeVisible({ timeout: 20_000 });

  await page.getByLabel("Your question").fill("how many annual leave days do I get?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Employees receive 24 days")).toBeVisible({ timeout: 15_000 });
  const chip = page.getByRole("button", { name: "Open source 1" }).first();
  await expect(chip).toBeVisible();
  await chip.click();
  await expect(page.getByRole("complementary", { name: "Source" })).toContainText("leave_policy.txt");
  await expect(page.getByRole("complementary", { name: "Source" }).locator("mark")).toContainText("24 days");

  await page.getByRole("button", { name: "Debug" }).click();
  await expect(page.getByRole("complementary", { name: "Debug" })).toContainText("similarity");

  // follow-up gets rewritten using the history
  await page.getByLabel("Your question").fill("what about carry over?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/searched for: “how many annual leave days carry over”/)).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByRole("button", { name: /Leave|how many/ }).first()).toBeVisible(); // session appears in the list

  await nav(page, "Index").click();
  await expect(page.getByRole("cell", { name: "hr/leave_policy.txt", exact: true })).toBeVisible();

  await nav(page, "Evaluation").click();
  await page.getByRole("button", { name: "Run sweep" }).click();
  await expect(page.getByRole("cell", { name: "1.00" }).first()).toBeVisible({ timeout: 20_000 });
});
