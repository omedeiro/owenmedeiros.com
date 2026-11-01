# Habits: one-time setup

The credentials, secrets, LaunchAgent and iOS Shortcuts each habit source needs before
the pipeline in `docs/habits-pipeline.md` can run. Moved here verbatim from the
"One-time setup" list that used to live in `AGENTS.md`; the `habits-data` skill
(`.claude/skills/habits-data/SKILL.md`) covers what each script does once this is in place.

1. **Strava** — create an app at <https://www.strava.com/settings/api>. Set
   **Authorization Callback Domain** to exactly `localhost` (no scheme, port, or path);
   Website can be anything. Then put `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` in
   `scripts/.env` and run `python scripts/fetch_strava.py --auth`, which opens the
   browser, catches the redirect on port 8721, and saves the refresh token.

   Do **not** copy the refresh token displayed on the API settings page. That one is
   permanently scoped to `read` and cannot list activities — it fails later with
   `401 activity:read_permission missing`. Only the `--auth` flow issues a token with
   `activity:read_all`, and the private-activity box on Strava's consent screen must
   stay ticked. `--auth --manual` falls back to pasting the redirect URL by hand.
2. **GitHub** — create a classic PAT with `read:user`. For private contributions also
   add `repo` and enable Settings → Profile → "Include private contributions".
3. **Repository secrets** — add `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`,
   `STRAVA_REFRESH_TOKEN`, and `GH_CONTRIB_TOKEN`. Optionally add `GH_ADMIN_TOKEN`
   (a PAT with `secrets:write`) so the workflow can store rotated Strava tokens itself;
   without it the job warns and you update `STRAVA_REFRESH_TOKEN` by hand.
4. **Screen time and sleep** — handled by the `com.owenmedeiros.habits` LaunchAgent,
   which runs `scripts/habits_daily.py` and commits to `main` only. Install it from the
   template in the repo, from the repo root — launchd does not expand `~` or `$HOME`,
   so the absolute paths are substituted in:

   ```bash
   mkdir -p ~/Library/LaunchAgents
   tmp=$(mktemp -t habits.plist)
   sed -e "s|{{HOME}}|$HOME|g" -e "s|{{REPO}}|$(pwd)|g" \
     scripts/com.owenmedeiros.habits.plist > "$tmp" \
     && plutil -lint "$tmp" \
     && mv "$tmp" ~/Library/LaunchAgents/com.owenmedeiros.habits.plist
   launchctl bootout gui/$(id -u)/com.owenmedeiros.habits 2>/dev/null
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.owenmedeiros.habits.plist
   ```

   **Build it in a temp file and move it into place**; do not redirect straight onto the
   installed plist. The shell creates the target and truncates it *before* running the
   command on the left, so any failure — the template not on the branch you have checked
   out, a typo in the path — leaves a 0-byte plist behind, and a 0-byte plist unloads the
   service without saying anything. That is exactly how the agent went dark on
   2026-09-03. `plutil -lint` between the two steps means a malformed substitution is
   caught before it can replace a working file.

   It collects three times — at login, at 12:00, and at 23:00 — rather than once at
   23:00. `knowledgeC.db` and Biome are pruned to roughly four weeks, so a night the Mac
   was shut is history nothing can recover afterwards; the extra slots mean a missed
   23:00 is picked up at noon and a Mac that was off through both is caught at the next
   login. Re-running costs nothing, since `write_habit` merges and `habits_daily.py`
   skips the commit when no day changed.

   It needs **Full Disk Access on `/usr/bin/python3`**, the interpreter the plist names
   (System Settings → Privacy & Security → Full Disk Access → **+** → ⌘⇧G →
   `/usr/bin/python3`). The grant is per-binary and it has to be on that exact path:
   `/usr/bin/python3` is a stub sharing an inode with `/usr/bin/git` that hands off to
   the Command Line Tools interpreter, and it is tempting to conclude from that that the
   grant lands on the wrong binary — but this machine grants and honours it on the stub
   path. Pointing the plist at the resolved CLT binary instead failed immediately with
   "authorization denied", because nothing ever granted *that* path. Check rather than
   reason about it:

   ```bash
   sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" \
     "select client, auth_value from access
        where service = 'kTCCServiceSystemPolicyAllFiles'"
   ```

   `auth_value` 2 is allowed. A working Terminal run proves nothing here: interactive
   shells have their TCC decisions attributed to Terminal, so verify the agent itself
   with `launchctl kickstart -p gui/$(id -u)/com.owenmedeiros.habits` and read
   `~/Library/Logs/habits-daily.log`.

   The plist also sets `EnvironmentVariables` → `PATH` so that `/opt/homebrew/bin` is on
   it. launchd's default `PATH` is `/usr/bin:/bin:/usr/sbin:/sbin`, which has no
   `git-lfs`; see [Git LFS](#git-lfs) for what that breaks.
5. **Stretching, daily** — build the iOS Shortcut in
   `docs/bend-stretching-shortcut.md` and schedule it. That is the whole pipeline:
   Bend → Apple Health → Shortcut → `repository_dispatch` → `stretching.yml` → deploy.
   Check Bend → Settings → Apple Health is granted first, or the Shortcut finds nothing.
6. **Stretching and sleep, in bulk** — on iPhone: Health → profile → Export All Health
   Data, then `python scripts/import_health.py ~/Downloads/export.zip` and commit.
   One pass fills in both habits, and is the way to catch up a long gap.
7. **Stretching before the sync date** — add rows to `scripts/bend-history.csv` from
   Bend's Recent History screen and run `python scripts/backfill_stretching.py`.
   Only needed for sessions predating step 5; Bend's Health connection writes from the
   day it was enabled onward and never backfills.
