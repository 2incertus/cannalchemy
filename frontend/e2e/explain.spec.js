import { test, expect } from "@playwright/test";

test.describe("Strain Explanation", () => {
  test("explain endpoint returns response", async ({ request }) => {
    // Get a strain name first
    const listRes = await request.get("http://localhost:8421/strains?limit=1");
    const listData = await listRes.json();
    const name = listData.strains[0].name;

    const res = await request.get(
      `http://localhost:8421/strains/${encodeURIComponent(name)}/explain`
    );
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    // Explanation may be null if LLM not configured — just verify structure
    expect(data).toHaveProperty("explanation");
    expect(data).toHaveProperty("provider");
    expect(data).toHaveProperty("cached");
  });

  test("strain detail page loads without explanation errors", async ({ page }) => {
    // Get a strain name via API
    const listRes = await page.request.get("http://localhost:8421/strains?limit=1");
    const listData = await listRes.json();
    const name = listData.strains[0].name;

    await page.goto(`/strain/${encodeURIComponent(name)}`);
    // Page should load successfully (explanation may or may not appear depending on LLM config)
    await expect(page.getByText(name)).toBeVisible({ timeout: 10000 });
    // No error state
    await expect(page.getByText("Strain Not Found")).not.toBeVisible();
  });
});
