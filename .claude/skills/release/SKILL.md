---
name: release
description: Use when asked to ship, release, bump the version, update the changelog, or open/merge a PR in this repo.
---

# Release ritual for owenmedeiros.com

Every non-trivial change (content edits, new pages, config, scripts) ships through the
same seven steps. Deploys happen automatically when `main` changes (Cloudflare Workers
Builds runs `npm run build`), so a merge *is* a deploy — do not merge anything that is not
ready to be live.

## 1. Branch

Never commit on `main`. From an up-to-date `main`:

```bash
git checkout main && git pull
git checkout -b feature/<short-slug>
```

## 2. Version bump

Edit `"version"` in `package.json` (semver). Read the file fully *before* opening it for
writing — `open(p,'w').write(open(p).read()...)` truncates first and broke the build in
2.1.2.

- **patch** (default) — content tweaks, copy and link edits, asset updates, data fixes.
- **minor** — a new page, a new feature, a new script, new tests or a new skill.
- **major** — site-wide redesign or migration only.

## 3. Changelog

Add a new entry at the **top** of `CHANGELOG.md`, below the `# Changelog` heading:

```markdown
## x.y.z — YYYY-MM-DD

### Added
- ...

### Changed
- ...

### Removed
- ...
```

Use only the subsections that apply. Entries are prose sentences about what the reader of
the site or the next agent will notice, not a list of file names. Match the existing
entries' tone; no trailing full stop on a one-sentence bullet is the house style.

## 4. Verify

```bash
npm run build                      # must exit 0 and write dist/
grep -rl katex-error dist/         # must print NOTHING
python3 -m unittest discover -s tests -v
python3 scripts/check_agent_env.py \
  --require-deny 'Bash(git push origin main:*)' \
  --require-deny 'Bash(git push -f:*)' \
  --require-deny 'Bash(git push --force:*)' \
  --require-deny 'Bash(gh pr merge --squash:*)' \
  --require-deny 'Bash(gh pr merge --rebase:*)' \
  --require-deny 'Bash(launchctl:*)' \
  --require-deny 'Bash(sqlite3 /Library/Application Support/com.apple.TCC:*)' \
  --ignore-path src/pages/section/page-name.md --ignore-path docs/figures/gallery_3d/render.py
```

The `katex-error` grep is not optional: a display-math fence opened on the same line as
its expression renders the rest of the page into one red `<span>` while `astro build`
still exits 0. `.github/workflows/ci.yml` runs all four on every PR, so a red PR means one
of these failed — read the job, do not retry blindly.

## 5. One commit

Exactly one commit holding the change, the version bump and the changelog entry. Concise
imperative subject line (`Add release skill and habit tests`), body optional. If the
session's attribution lines are given, they go at the end of the message.

## 6. Pull request

```bash
git push -u origin feature/<short-slug>
gh pr create --base main --title "<subject>" --body-file <body.md>
```

If GraphQL is blocked, the REST endpoint works:
`gh api repos/omedeiro/owenmedeiros.com/pulls -f title='...' -f head='<branch>' -f base='main' -F body=@body.md`.
The body says what changed and why, lists the verification commands with their last line
of output, and names anything that needs Owen (a secret, a decision, a machine).

## 7. Merge — merge commit only, and only when told

Wait for Owen's say-so and for CI to be green. Then:

```bash
gh pr merge --merge --delete-branch
git checkout main && git pull
```

Always a **merge commit**, never squash or rebase — the history is a chain of merge
commits and `.claude/settings.json` denies `gh pr merge --squash` and `--rebase` for that
reason. Pushing to `main` directly is denied too; only the data workflows
(`habits.yml`, `stretching.yml`, `weight.yml`) commit there, and only data.

## Git LFS

PDFs are LFS-tracked (`.gitattributes`). If a push fails with "git-lfs not found", run
`git lfs install` and push again. Never commit a PDF from a clone that only holds LFS
pointer stubs.
