/**
 * ResearchLens — Comprehensive Headless Playwright E2E Spec using Topic "aiml"
 * Corresponds to tests/e2e/test_aiml_comprehensive_audit.py
 */

import { test, expect } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:3000';
const BACKEND_URL = 'http://localhost:8000';

test.describe('ResearchLens E2E Suite — Topic: aiml', () => {

  test('Section A: Application Startup & Navigation', async ({ page }) => {
    await page.goto(FRONTEND_URL);
    await expect(page).toHaveTitle(/ResearchLens/);

    // Verify main navigation tabs
    const tabs = ['Explore', 'PDF Manuscript', 'Evolution & Gaps', 'Saved Library', 'DRIUT Alerts'];
    for (const tab of tabs) {
      await expect(page.locator(`nav.nav-tabs button:has-text("${tab}")`)).toBeVisible();
    }
  });

  test('Section C: Authentication Controls', async ({ page }) => {
    await page.goto(FRONTEND_URL);
    await page.locator("button:has-text('Sign In')").click();
    await expect(page.locator("text=Researcher Access")).toBeVisible();

    // Invalid credentials rejection
    await page.locator(".modal-dialog input[type='text']").fill("invalid_user_probe");
    await page.locator(".modal-dialog input[type='password']").fill("wrong_password");
    await page.locator(".modal-dialog button[type='submit']").click();
    await expect(page.locator(".modal-dialog span:has-text('Authentication failed'), .modal-dialog span:has-text('Invalid')")).toBeVisible();

    // Auto-fill demo login
    await page.locator(".modal-dialog button:has-text('Auto-fill')").click();
    await page.locator(".modal-dialog button[type='submit']").click();
    await expect(page.locator(".modal-overlay")).toBeHidden();
    await expect(page.locator("header.header-bar span:has-text('admin')")).toBeVisible();

    // Logout
    await page.locator("header.header-bar button:has-text('(Sign Out)')").click();
    await expect(page.locator("header.header-bar button:has-text('Sign In')")).toBeVisible();
  });

  test('Section D: Research Search using Topic "aiml"', async ({ page }) => {
    await page.goto(FRONTEND_URL);
    const extToggle = page.locator("label:has-text('Live Remote Discovery') input[type='checkbox']");
    expect(await extToggle.isChecked()).toBe(false);

    await page.locator("input.main-search-input").fill("aiml");
    await page.locator("button.search-action-btn").click();

    await page.waitForSelector(".results-header", { timeout: 15000 });
    const cards = page.locator(".paper-card");
    expect(await cards.count()).toBeGreaterThan(0);
  });

  test('Section E & F: Paper Evidence & Summary Modals', async ({ page }) => {
    await page.goto(FRONTEND_URL);
    await page.locator("input.main-search-input").fill("aiml");
    await page.locator("button.search-action-btn").click();
    await page.waitForSelector(".paper-card");

    // Evidence Modal
    const firstCard = page.locator(".paper-card").first();
    await firstCard.locator("button:has-text('Evidence')").click();
    await page.waitForSelector("text=Grounded Research Intelligence");
    await page.locator("button[aria-label='Close modal'], .modal-close-btn").first().click();

    // Summary Modal
    await firstCard.locator("button:has-text('AI Summary')").click();
    await page.waitForSelector("text=ResearchLens Synthesis");
    await page.locator(".modal-card button.modal-close-btn, button:has-text('✕')").first().click();
  });

  test('Section G: Multi-Paper Comparison Matrix', async ({ page }) => {
    await page.goto(FRONTEND_URL);
    await page.locator("input.main-search-input").fill("aiml");
    await page.locator("button.search-action-btn").click();
    await page.waitForSelector(".paper-card");

    const cards = page.locator(".paper-card");
    await cards.nth(0).locator("label:has-text('Compare') input[type='checkbox']").check();
    await cards.nth(1).locator("label:has-text('Compare') input[type='checkbox']").check();

    await page.locator("button:has-text('Compare (2)')").click();
    await page.waitForSelector("text=Structured Research Paper Comparison");
    await page.locator("button[aria-label='Close Comparison'], .modal-close-btn").first().click();
  });

  test('Section H, I & J: Research Evolution, Gaps & Assistant', async ({ page }) => {
    await page.goto(FRONTEND_URL);
    await page.locator("nav.nav-tabs button:has-text('Evolution & Gaps')").click();

    // Timeline
    await page.locator("button:has-text('Timeline')").click();
    await page.waitForSelector("text=Total Papers:");

    // Graph
    await page.locator("button:has-text('Relationship Graph')").click();
    await expect(page.locator("input[type='range']")).toBeVisible();

    // Gaps
    await page.locator("button:has-text('Gap Discovery')").click();
    await page.waitForSelector("text=Essential Scientific Truthfulness & Discovery Disclosure");

    // Assistant
    await page.locator("button:has-text('Assistant')").click();
    const asstInput = page.locator("input[placeholder*='Ask any question']");
    await asstInput.fill("What are the key limitations reported for AI/ML models?");
    await page.locator("button:has-text('Ask Assistant')").click();
    await page.waitForSelector("text=Evidence-Grounded Synthesis", { timeout: 40000 });
  });

  test('Section L: Saved Literature Sanctuary & DRIUT Alerts Views', async ({ page }) => {
    await page.goto(FRONTEND_URL);
    await page.locator("nav.nav-tabs button:has-text('Saved Library')").click();
    await expect(page.locator("text=Private Literature Sanctuary")).toBeVisible();

    await page.locator("nav.nav-tabs button:has-text('DRIUT Alerts')").click();
    await expect(page.locator("text=Dynamic Research Impact Update Tracker")).toBeVisible();
  });

  test('Section N: Error Handling & Robustness', async ({ page }) => {
    await page.goto(FRONTEND_URL);
    await page.locator("input.main-search-input").fill("xyzzyq999nonexistentquery");
    await page.locator("button.search-action-btn").click();
    await page.waitForSelector(".results-header");
  });
});
