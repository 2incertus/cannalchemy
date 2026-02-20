import { test, expect } from "@playwright/test";

test.describe("Explorer Page", () => {
  test("renders effect picker with categories", async ({ page }) => {
    await page.goto("/explore");
    await expect(page.getByText("What do you want to feel?")).toBeVisible();
    // Has category headings
    await expect(page.getByText("Positive")).toBeVisible();
    await expect(page.getByText("Medical")).toBeVisible();
  });

  test("shows popular strains by default", async ({ page }) => {
    await page.goto("/explore");
    // Wait for strain cards to load (default empty-selection shows popular strains)
    await expect(page.locator(".card").first()).toBeVisible({ timeout: 10000 });
    const cards = page.locator(".card");
    expect(await cards.count()).toBeGreaterThan(0);
  });

  test("type filter pills work", async ({ page }) => {
    await page.goto("/explore");
    // Click indica filter
    await page.getByRole("button", { name: "indica" }).click();
    // Wait for results to reload
    await page.waitForTimeout(1000);
    // Should still have cards
    const cards = page.locator(".card");
    expect(await cards.count()).toBeGreaterThan(0);
  });

  test("selecting effects triggers match search", async ({ page }) => {
    await page.goto("/explore");
    // Wait for effects to load
    await page.waitForTimeout(2000);
    // Find and click the first effect chip button
    const chips = page.locator("button").filter({ hasText: /relaxed|happy|euphoric/i });
    if ((await chips.count()) > 0) {
      await chips.first().click();
      // Wait for match results
      await page.waitForTimeout(8000); // match is slower
      await expect(page.getByText(/effect.* selected/i)).toBeVisible();
    }
  });

  test("strain card links to detail page", async ({ page }) => {
    await page.goto("/explore");
    // Wait for cards to load
    await expect(page.locator(".card").first()).toBeVisible({ timeout: 10000 });
    // Click the first "Details →" link
    const detailLink = page.locator("a").filter({ hasText: "Details →" }).first();
    await detailLink.click();
    await expect(page).toHaveURL(/\/strain\//);
  });
});

test.describe("Strain Detail Page", () => {
  test("loads strain profile", async ({ page }) => {
    test.setTimeout(90000); // First load builds knowledge graph
    // Use a known common strain — search for one with alphabetical name
    const res = await page.request.get("http://localhost:8421/strains?q=blue&limit=1");
    const data = await res.json();
    const strainName = data.strains[0]?.name;
    if (!strainName) return;

    await page.goto(`/strain/${encodeURIComponent(strainName)}`);

    // Wait for page to load (graph build can take 30s+ on first call)
    await expect(page.getByText("Terpene Profile")).toBeVisible({ timeout: 60000 });
    // Predicted Effects section
    await expect(page.getByText("Predicted Effects")).toBeVisible();
    // Molecular Pathways section
    await expect(page.getByText("Molecular Pathways")).toBeVisible();
    // Back link
    await expect(page.getByText("← Back to Explorer")).toBeVisible();
  });

  test("shows 404 for nonexistent strain", async ({ page }) => {
    await page.goto("/strain/NonexistentStrain12345");
    await expect(page.getByText("Strain Not Found")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Back to Explorer")).toBeVisible();
  });

  test("back link returns to explorer", async ({ page }) => {
    const res = await page.request.get("http://localhost:8421/strains?limit=1");
    const data = await res.json();
    const strainName = data.strains[0].name;

    await page.goto(`/strain/${encodeURIComponent(strainName)}`);
    await expect(page.getByText("Terpene Profile")).toBeVisible({ timeout: 15000 });

    await page.getByText("← Back to Explorer").click();
    await expect(page).toHaveURL("/explore");
  });
});
