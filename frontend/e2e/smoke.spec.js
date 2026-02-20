import { test, expect } from "@playwright/test";

test.describe("Landing Page", () => {
  test("renders hero section with title and CTA", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h1")).toContainText("CANNALCHEMY");
    await expect(page.getByText("The science behind how you feel")).toBeVisible();
    const cta = page.getByRole("link", { name: "Explore Effects →" });
    await expect(cta).toBeVisible();
    await expect(cta).toHaveAttribute("href", "/explore");
  });

  test("hero radar SVG renders with polygons", async ({ page }) => {
    await page.goto("/");
    // The HeroRadar is the only SVG with polygon children (lucide icons don't have polygons)
    const polygons = page.locator("svg polygon");
    expect(await polygons.count()).toBeGreaterThanOrEqual(4); // 3 rings + 1 data polygon
  });

  test("feature cards render below fold", async ({ page }) => {
    await page.goto("/");
    // Scroll down to trigger IntersectionObserver
    const heading = page.getByRole("heading", { name: "Predict" });
    await heading.scrollIntoViewIfNeeded();
    await expect(heading).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole("heading", { name: "Trace" })).toBeVisible();
    // 3 feature cards total
    const cards = page.locator(".card");
    expect(await cards.count()).toBe(3);
  });

  test("stats line shows data from API", async ({ page }) => {
    await page.goto("/");
    const stats = page.locator(".font-data").first();
    await expect(stats).toContainText(/strains/);
    await expect(stats).toContainText(/molecules/);
    await expect(stats).toContainText(/effects/);
  });
});

test.describe("Navigation", () => {
  test("nav bar renders with logo and links", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("⚗ CANNALCHEMY")).toBeVisible();
    // Use exact matching to avoid CTA button conflict
    const nav = page.locator("nav");
    await expect(nav.getByRole("link", { name: "Explore", exact: true })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Compare" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Graph" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Data" })).toBeVisible();
  });

  test("navigate to explore page via nav", async ({ page }) => {
    await page.goto("/");
    await page.locator("nav").getByRole("link", { name: "Explore", exact: true }).click();
    await expect(page).toHaveURL("/explore");
    await expect(page.getByText("What do you want to feel?")).toBeVisible();
  });

  test("navigate to compare page", async ({ page }) => {
    await page.goto("/");
    await page.locator("nav").getByRole("link", { name: "Compare" }).click();
    await expect(page).toHaveURL("/compare");
    await expect(page.getByText("Compare Strains")).toBeVisible();
  });

  test("navigate to graph page", async ({ page }) => {
    await page.goto("/");
    await page.locator("nav").getByRole("link", { name: "Graph" }).click();
    await expect(page).toHaveURL("/graph");
    await expect(page.getByText("Knowledge Graph")).toBeVisible();
  });

  test("navigate to data quality page", async ({ page }) => {
    await page.goto("/");
    await page.locator("nav").getByRole("link", { name: "Data" }).click();
    await expect(page).toHaveURL("/quality");
    await expect(page.getByRole("heading", { name: "Data Quality" })).toBeVisible({ timeout: 15000 });
  });

  test("logo navigates home", async ({ page }) => {
    await page.goto("/explore");
    await page.getByText("⚗ CANNALCHEMY").click();
    await expect(page).toHaveURL("/");
    await expect(page.locator("h1")).toContainText("CANNALCHEMY");
  });
});

test.describe("API Integration", () => {
  test("stats endpoint returns data", async ({ request }) => {
    const res = await request.get("http://localhost:8421/stats");
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data).toHaveProperty("total_strains");
    expect(data).toHaveProperty("molecules");
    expect(data).toHaveProperty("effects");
    expect(data.total_strains).toBeGreaterThan(0);
  });

  test("strains endpoint returns list", async ({ request }) => {
    const res = await request.get("http://localhost:8421/strains?limit=5");
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data).toHaveProperty("strains");
    expect(data.strains.length).toBeGreaterThan(0);
    expect(data.strains.length).toBeLessThanOrEqual(5);
  });

  test("effects endpoint returns predictions", async ({ request }) => {
    const res = await request.get("http://localhost:8421/effects");
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data).toHaveProperty("effects");
    expect(data.effects.length).toBeGreaterThan(0);
  });

  test("graph endpoint returns nodes and edges", async ({ request }) => {
    test.setTimeout(90000); // Graph build is expensive on first call
    const res = await request.get("http://localhost:8421/graph");
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data).toHaveProperty("nodes");
    expect(data).toHaveProperty("edges");
    expect(data.nodes.length).toBeGreaterThan(0);
    expect(data.edges.length).toBeGreaterThan(0);
  });

  test("match endpoint finds strains", async ({ request }) => {
    test.setTimeout(180000); // prediction cache build takes 45-90s on N100 with production DB
    const res = await request.post("http://localhost:8421/match", {
      data: { effects: ["relaxed"], type: "indica", limit: 3 },
    });
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data).toHaveProperty("strains");
    expect(data.strains.length).toBeGreaterThan(0);
    expect(data.strains[0]).toHaveProperty("score");
  });

  test("strain detail endpoint works", async ({ request }) => {
    // First get a strain name from the list
    const listRes = await request.get("http://localhost:8421/strains?limit=1");
    const listData = await listRes.json();
    const name = listData.strains[0].name;

    const res = await request.get(`http://localhost:8421/strains/${encodeURIComponent(name)}`);
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.name).toBe(name);
    expect(data).toHaveProperty("compositions");
    expect(data).toHaveProperty("predicted_effects");
  });
});
