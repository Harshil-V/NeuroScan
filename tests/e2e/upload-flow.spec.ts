import { test, expect } from "@playwright/test";
import { execSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("upload a synthetic DICOM and see it in the study list", async ({ page }) => {
  const dir = mkdtempSync(join(tmpdir(), "neuroscan-"));
  const dicomPath = join(dir, "x.dcm");
  const repoRoot = process.cwd().replace(/\/tests\/e2e$/, "");
  execSync(
    `uv run --directory services/api-service python ../../scripts/generate-synthetic-dicom.py "${dicomPath}"`,
    { stdio: "inherit", cwd: repoRoot }
  );

  await page.goto("/upload");
  await page.locator('input[type="file"]').setInputFiles(dicomPath);
  await expect(page.getByTestId("upload-success")).toBeVisible({ timeout: 15_000 });

  await page.goto("/studies");
  const firstRow = page.locator("tbody tr").first();
  await expect(firstRow).toBeVisible();
  await firstRow.click();

  const img = page.locator("img").first();
  await expect(img).toBeVisible();
  const naturalWidth = await img.evaluate((el) => (el as HTMLImageElement).naturalWidth);
  expect(naturalWidth).toBeGreaterThan(0);

  await page.goto("/audit");
  await expect(page.getByText("dicom_uploaded").first()).toBeVisible();
});
