import { chromium, type BrowserContext, type Page } from "playwright";
import { resolve } from "node:path";
import { mkdirSync } from "node:fs";

const PROFILE_DIR = resolve(process.env.PLAYWRIGHT_PROFILE ?? "./playwright-profile");
const HEADED = (process.env.PLAYWRIGHT_HEADED ?? "true").toLowerCase() !== "false";

mkdirSync(PROFILE_DIR, { recursive: true });

export async function launchContext(): Promise<BrowserContext> {
  return chromium.launchPersistentContext(PROFILE_DIR, {
    headless: !HEADED,
    viewport: { width: 1280, height: 900 },
  });
}

export async function isLoggedIn(page: Page): Promise<boolean> {
  await page.goto("https://x.com/home", { waitUntil: "domcontentloaded" });
  const url = page.url();
  return !/\/(login|i\/flow\/login)/.test(url);
}

/**
 * Open a DM conversation with the given handle and send the message.
 * Throws on failure. Caller is responsible for rate limiting between calls.
 */
export async function sendDirectMessage(
  page: Page,
  handle: string,
  body: string,
): Promise<void> {
  const clean = handle.replace(/^@/, "");
  await page.goto(`https://x.com/messages/compose?recipient_id=${encodeURIComponent(clean)}`, {
    waitUntil: "domcontentloaded",
  });

  // X's compose flow requires picking the user from the search results.
  const searchBox = page.getByTestId("searchPeople").or(page.getByRole("textbox").first());
  await searchBox.waitFor({ timeout: 15000 });
  await searchBox.click();
  await searchBox.fill(clean);

  const userResult = page
    .getByTestId("TypeaheadUser")
    .filter({ hasText: new RegExp(`@${clean}\\b`, "i") })
    .first();
  await userResult.waitFor({ timeout: 10000 });
  await userResult.click();

  const nextBtn = page.getByTestId("nextButton");
  await nextBtn.waitFor({ timeout: 5000 });
  await nextBtn.click();

  const editor = page.getByTestId("dmComposerTextInput");
  await editor.waitFor({ timeout: 15000 });
  await editor.click();
  await editor.fill(body);

  const sendBtn = page.getByTestId("dmComposerSendButton");
  await sendBtn.waitFor({ timeout: 5000 });
  await sendBtn.click();

  // Confirm the message landed by waiting for the editor to clear.
  await page.waitForFunction(
    () => {
      const el = document.querySelector('[data-testid="dmComposerTextInput"]');
      return !el || (el as HTMLElement).innerText.trim() === "";
    },
    { timeout: 10000 },
  );
}

export async function jitterDelay(baseMs: number): Promise<void> {
  const wait = baseMs + Math.floor(Math.random() * baseMs);
  await new Promise((r) => setTimeout(r, wait));
}
