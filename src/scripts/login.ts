import { launchContext } from "../lib/twitter";

/**
 * Opens a browser window so the user can log in to X manually.
 * Cookies persist in PLAYWRIGHT_PROFILE for the worker to reuse.
 * Close the browser window when done.
 */
async function main() {
  process.env.PLAYWRIGHT_HEADED = "true";
  const ctx = await launchContext();
  const page = await ctx.newPage();
  await page.goto("https://x.com/login");
  console.log("Log in to X in the opened browser, then close the window when done.");
  await new Promise<void>((resolve) => {
    ctx.on("close", () => resolve());
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
