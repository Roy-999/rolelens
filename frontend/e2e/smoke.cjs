/* Actual browser + API integration checks against the running Compose stack. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

(async () => {
  const baseURL = process.env.BASE_URL || "http://localhost:8080";
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.BROWSER_CHANNEL ? { channel: process.env.BROWSER_CHANNEL } : {}),
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("response", (response) => {
    if (response.url().startsWith(baseURL + "/api/") && response.status() >= 500)
      errors.push(`${response.status()} ${response.url()}`);
  });
  const screenshotsOnly = process.argv.includes("--screenshots-only");
  const runId = Date.now().toString(36);
  const reviewedName = `Quinn Taylor reviewed ${runId}`;
  const editedName = `Quinn Taylor edited ${runId}`;
  const reviewedJob = `Reviewed Data Engineer ${runId}`;
  const output = path.resolve(__dirname, "../../docs/screenshots");
  fs.mkdirSync(output, { recursive: true });
  async function nav(name) {
    await page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("button", { name, exact: true })
      .click();
  }
  try {
    await page.goto(baseURL);
    await page.getByRole("heading", { name: "See the person. Find the possibility." }).waitFor();
    await page.evaluate(() => document.fonts.ready);
    assert.equal((await page.request.get(baseURL + "/api/ready")).status(), 200);
    assert.equal((await page.request.get(baseURL + "/api/docs")).status(), 200);
    const baseline = (await (await page.request.get(baseURL + "/api/candidates")).json())
      .total_candidates;
    if (screenshotsOnly)
      await page.screenshot({ path: path.join(output, "overview.png"), fullPage: true });
    if (!screenshotsOnly) {
      await page.getByRole("button", { name: "Try sample workflow" }).click();
      await page.getByRole("heading", { name: "Review extracted details" }).waitFor();
      assert.equal(await page.getByLabel("Name", { exact: true }).inputValue(), "Quinn Taylor");
      await page.getByLabel("Name", { exact: true }).fill(reviewedName);
      await page.getByRole("button", { name: "Save candidate", exact: true }).click();
      await page.getByRole("heading", { name: "1 candidate saved" }).waitFor();
      await page.getByRole("button", { name: "View candidates", exact: true }).click();
      await page.getByRole("button", { name: reviewedName, exact: true }).click();
      await page.getByRole("button", { name: "Edit record", exact: true }).click();
      await page.getByLabel("Name", { exact: true }).fill(editedName);
      await page.getByRole("button", { name: "Save changes", exact: true }).click();
      await page.getByLabel("Search candidates").fill(editedName);
      await page.getByRole("button", { name: editedName, exact: true }).waitFor();
      assert.equal(
        (await (await page.request.get(baseURL + "/api/candidates")).json()).total_candidates,
        baseline + 1,
      );
      await nav("Candidates");
      await page.getByRole("button", { name: "Bulk intake" }).click();
      const content = fs.readFileSync(path.resolve(__dirname, "../public/samples/resume.txt"));
      await page.getByLabel("Upload documents", { exact: true }).setInputFiles([
        {
          name: "batch-one.txt",
          mimeType: "text/plain",
          buffer: Buffer.from(content.toString().replace("Quinn Taylor", "Avery Demo")),
        },
        {
          name: "batch-two.txt",
          mimeType: "text/plain",
          buffer: Buffer.from(content.toString().replace("Quinn Taylor", "Jordan Demo")),
        },
      ]);
      await page.getByRole("heading", { name: "Review extracted details" }).waitFor();
      await page.getByRole("button", { name: "Save & review next", exact: true }).click();
      await page.getByText("Document 2 of 2", { exact: false }).waitFor();
      await page.getByRole("button", { name: "Save candidate", exact: true }).click();
      await page.getByRole("heading", { name: "2 candidates saved" }).waitFor();
      await nav("Job orders");
      await page.getByRole("button", { name: "Add job order", exact: true }).click();
      await page.getByRole("button", { name: "Use sample job order", exact: true }).click();
      await page.getByRole("heading", { name: "Review extracted details" }).waitFor();
      await page.getByLabel("Job Title", { exact: true }).fill(reviewedJob);
      await page.getByRole("button", { name: "Save job order", exact: true }).click();
      await page.getByRole("heading", { name: "1 job order saved" }).waitFor();
      await page.getByRole("button", { name: "View job orders", exact: true }).click();
      await page.getByRole("button", { name: reviewedJob, exact: true }).click();
      await page.getByRole("button", { name: "Edit record" }).click();
      await page.getByLabel("Organization Name", { exact: true }).fill("Fictional Browser Works");
      await page.getByRole("button", { name: "Save changes" }).click();
      await page.getByLabel("Search job orders").fill("Fictional Browser Works");
      await page.getByRole("button", { name: reviewedJob, exact: true }).waitFor();
    }
    await nav("Matching studio");
    const jobs = (await (await page.request.get(baseURL + "/api/job-orders")).json()).jobs;
    const sampleJob = jobs.find((j) => j.job_order_id === "RL-JOB-001");
    await page.getByLabel("Saved job order", { exact: true }).selectOption(sampleJob.id);
    await page.getByRole("button", { name: "Find matching candidates", exact: true }).click();
    await page.getByText("Keyword only", { exact: true }).waitFor();
    assert.ok((await page.locator(".match-card").count()) >= 3);
    if (screenshotsOnly)
      await page.screenshot({ path: path.join(output, "matching.png"), fullPage: true });
    await page.getByLabel("Candidate location", { exact: true }).selectOption("Austin");
    await page.getByRole("button", { name: "Find matching candidates", exact: true }).click();
    await page.locator(".match-card").first().waitFor();
    assert.ok(
      (await page.locator(".match-meta").allTextContents()).every((s) => s.includes("Austin")),
    );
    await nav("Integrations");
    await page.getByText("Optional · disabled", { exact: true }).waitFor();
    assert.equal((await page.request.get(baseURL + "/api/gmail/login")).status(), 409);
    await nav("Candidates");
    await page.getByLabel("Search candidates").fill("zz-no-records-exist");
    await page.getByRole("heading", { name: "No records found" }).waitFor();
    await nav("Overview");
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole("heading", { name: "See the person. Find the possibility." }).waitFor();
    assert.ok(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      "Mobile viewport must not overflow horizontally",
    );
    if (screenshotsOnly)
      await page.screenshot({ path: path.join(output, "mobile.png"), fullPage: true });
    await nav("Matching studio");
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await page.getByRole("button", { name: "Candidates", exact: true }).focus();
    await page.keyboard.press("Enter");
    await page.getByRole("heading", { name: /Candidate library/ }).waitFor();
    assert.deepEqual(errors, [], "Browser errors / failed API requests");
    console.log(
      screenshotsOnly
        ? "Desktop, matching, and mobile screenshots captured; responsive smoke checks passed."
        : "Browser workflow passed: intake, review, save, edit, bulk intake, job intake/edit, matching, location filtering, empty states, optional Gmail, and mobile navigation.",
    );
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
