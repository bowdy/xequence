# Agent Instructions

You're working inside the **WAT framework** (Workflows, Agents, Tools). This architecture separates concerns so that probabilistic AI handles reasoning while deterministic code handles execution. That separation is what makes this system reliable.

## The WAT Architecture

**Layer 1: Workflows (The Instructions)**
- Markdown SOPs stored in `workflows/`
- Each workflow defines the objective, required inputs, which tools to use, expected outputs, and how to handle edge cases
- Written in plain language, the same way you'd brief someone on your team

**Layer 2: Agents (The Decision-Maker)**
- This is your role. You're responsible for intelligent coordination.
- Read the relevant workflow, run tools in the correct sequence, handle failures gracefully, and ask clarifying questions when needed
- You connect intent to execution without trying to do everything yourself
- Example: If you need to pull data from a website, don't attempt it directly. Read `workflows/scrape_website.md`, figure out the required inputs, then execute `tools/scrape_single_site.py`

**Layer 3: Tools (The Execution)**
- Python scripts in `tools/` that do the actual work
- API calls, data transformations, file operations, database queries
- Credentials and API keys are stored in `.env`
- These scripts are consistent, testable, and fast

**Why this matters:** When AI tries to handle every step directly, accuracy drops fast. If each step is 90% accurate, you're down to 59% success after just five steps. By offloading execution to deterministic scripts, you stay focused on orchestration and decision-making where you excel.

## How to Operate

**1. Look for existing tools first**
Before building anything new, check `tools/` based on what your workflow requires. Only create new scripts when nothing exists for that task.

**2. Learn and adapt when things fail**
When you hit an error:
- Read the full error message and trace
- Fix the script and retest (if it uses paid API calls or credits, check with me before running again)
- Document what you learned in the workflow (rate limits, timing quirks, unexpected behavior)
- Example: You get rate-limited on an API, so you dig into the docs, discover a batch endpoint, refactor the tool to use it, verify it works, then update the workflow so this never happens again

**3. Keep workflows current**
Workflows should evolve as you learn. When you find better methods, discover constraints, or encounter recurring issues, update the workflow. That said, don't create or overwrite workflows without asking unless I explicitly tell you to. These are your instructions and need to be preserved and refined, not tossed after one use.

**4. Skills**
Before building, always look to see if there are any pre-existing 'skills' that you can pull from and use, here: https://skills.sh/

## The Self-Improvement Loop

Every failure is a chance to make the system stronger:
1. Identify what broke
2. Fix the tool
3. Verify the fix works
4. Update the workflow with the new approach
5. Move on with a more robust system

This loop is how the framework improves over time.

## File Structure

**What goes where:**
- **Deliverables**: Final outputs go to cloud services (Google Sheets, Slides, etc.) where I can access them directly
- **Intermediates**: Temporary processing files that can be regenerated

**Directory layout:**
```
.tmp/           # Temporary files (scraped data, intermediate exports). Regenerated as needed.
tools/          # Python scripts for deterministic execution
workflows/      # Markdown SOPs defining what to do and how
.env            # API keys and environment variables (NEVER store secrets anywhere else)
credentials.json, token.json  # Google OAuth (gitignored)
```

**Core principle:** Local files are just for processing. Anything I need to see or use lives in cloud services. Everything in `.tmp/` is disposable.

## Bottom Line

You sit between what I want (workflows) and what actually gets done (tools). Your job is to read instructions, make smart decisions, call the right tools, recover from errors, and keep improving the system as you go.

Stay pragmatic. Stay reliable. Keep learning.

---

## Train Sound Notification Hook

When Claude Code stops running and needs your input (permission prompts, questions, tool approvals), a custom train "choo-choo" sound plays automatically.

### Primary Method: CC Ring VSCode Extension (Native UI)

Claude Code's built-in hooks (`Notification`, `Stop`) **do not fire** in the VSCode extension's native UI panel (confirmed bug: GitHub #8985, #16114). The **CC Ring** extension bypasses this by registering hooks through VSCode's extension API.

**Already installed and configured.** Settings in VSCode (`Cmd+,` → search "cc-ring"):

```json
{
  "cc-ring.enabled": true,
  "cc-ring.sound": "custom",
  "cc-ring.customSoundPath": "/Users/admin/.claude/hooks/choo-choo.m4a",
  "cc-ring.volume": 75
}
```

**First-time setup** (one-time after install):
1. Open Command Palette (`Cmd+Shift+P`)
2. Run: `CC Ring: Install/Reinstall Hook`
3. Test: `CC Ring: Test Sound`

**Commands** (via Command Palette):
- `CC Ring: Test Sound` — preview the sound
- `CC Ring: Select Custom Sound` — pick a different audio file
- `CC Ring: Show Status` — check if hook is active
- `CC Ring: Install/Reinstall Hook` — reinstall if broken
- `CC Ring: Uninstall Hook` — remove the hook

### Backup Method: Shell Hooks (Terminal/CLI Mode)

If using Claude Code in terminal mode (`claude` in integrated terminal), the built-in hooks also work:

**Sound file**: `~/.claude/hooks/choo-choo.m4a`
**Script**: `~/.claude/hooks/play-sound.sh` (plays choo-choo.m4a, falls back to macOS Submarine.aiff)
**Config**: `~/.claude/settings.json` has `Notification` + `Stop` hooks pointing at the script
