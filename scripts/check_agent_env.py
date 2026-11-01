#!/usr/bin/env python3
"""Verify the repo's agentic environment is internally consistent.

Checks (each one is a line in the output, PASS or FAIL):

  settings      .claude/settings.json parses; every hook command it names exists
                and is executable; every rule in --require-deny / --require-allow
                is present.
  hooks         every file under .claude/hooks/ is executable and is referenced
                by .claude/settings.json (a hook nobody registered is dead code).
  skills        every .claude/skills/<name>/SKILL.md has YAML frontmatter with
                name == <name> and a non-empty description; every .claude/commands/*.md
                has a description.
  symlinks      every entry under .opencode/skills/ resolves, and the set of
                skill names under .opencode/skills/ equals the set under
                .claude/skills/ (when both directories exist).
  agents-md     AGENTS.md exists, is <= --max-agents-kb, and names every
                skill directory (so an agent can find them); if CLAUDE.md
                exists it contains "@AGENTS.md".
  stale         .github/copilot-instructions.md is absent or a one-line import
                of AGENTS.md.
  paths         every path-like token in AGENTS.md that looks like a repo file
                (contains '/' and an extension, no spaces, no glob) exists.
  commands      each command given with --run exits 0.

Usage:
  python3 scripts/check_agent_env.py [--max-agents-kb 12]
      [--require-deny 'Bash(gh pr merge:*)' ...] [--require-allow ...]
      [--run 'python -m pytest -q' ...] [--ignore-path firmware/src/secrets.h ...]

Exit status is the number of failed checks (0 = all green). Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS: list[tuple[str, bool, str]] = []


def record(group: str, ok: bool, msg: str) -> None:
    RESULTS.append((group, ok, msg))


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    block = text[3:end]
    out: dict[str, str] = {}
    key = None
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            out[key] = val.lstrip(">|").strip()
        elif key and line.startswith((" ", "\t")):
            out[key] = (out[key] + " " + line.strip()).strip()
    return out


def check_settings(require_deny: list[str], require_allow: list[str]) -> set[str]:
    """Return the set of hook command paths registered in settings.json."""
    path = ROOT / ".claude" / "settings.json"
    registered: set[str] = set()
    if not path.exists():
        record("settings", False, ".claude/settings.json is missing")
        return registered
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        record("settings", False, f".claude/settings.json does not parse: {e}")
        return registered
    record("settings", True, ".claude/settings.json parses")

    hooks = data.get("hooks", {})
    for event, matchers in hooks.items():
        for matcher in matchers:
            for hook in matcher.get("hooks", []):
                if hook.get("type") != "command":
                    continue
                cmd = hook.get("command", "")
                first = cmd.split()[0] if cmd.split() else ""
                first = first.replace("${CLAUDE_PROJECT_DIR}", str(ROOT)).replace(
                    "$CLAUDE_PROJECT_DIR", str(ROOT)
                )
                p = Path(first)
                if not p.is_absolute():
                    p = ROOT / p
                if p.exists():
                    registered.add(str(p.resolve()))
                    ok = os.access(p, os.X_OK)
                    record(
                        "settings",
                        ok,
                        f"{event} hook {p.relative_to(ROOT)} "
                        + ("is executable" if ok else "is NOT executable"),
                    )
                elif "/" in first:
                    record(
                        "settings", False, f"{event} hook command not found: {first}"
                    )
                else:
                    record(
                        "settings",
                        True,
                        f"{event} hook runs '{first}' (not a repo file; not checked)",
                    )

    perms = data.get("permissions", {})
    deny = set(perms.get("deny", []))
    allow = set(perms.get("allow", []))
    for rule in require_deny:
        record("settings", rule in deny, f"deny rule present: {rule}")
    for rule in require_allow:
        record("settings", rule in allow, f"allow rule present: {rule}")
    return registered


def check_hooks(registered: set[str]) -> None:
    hooks_dir = ROOT / ".claude" / "hooks"
    if not hooks_dir.exists():
        return
    for f in sorted(hooks_dir.iterdir()):
        if not f.is_file():
            continue
        record("hooks", os.access(f, os.X_OK), f"{f.relative_to(ROOT)} executable")
        record(
            "hooks",
            str(f.resolve()) in registered,
            f"{f.relative_to(ROOT)} registered in settings.json",
        )


def skill_dirs() -> list[Path]:
    d = ROOT / ".claude" / "skills"
    if not d.exists():
        return []
    return sorted(p for p in d.iterdir() if p.is_dir())


def check_skills() -> list[str]:
    names: list[str] = []
    for d in skill_dirs():
        md = d / "SKILL.md"
        if not md.exists():
            record("skills", False, f"{d.relative_to(ROOT)} has no SKILL.md")
            continue
        fm = frontmatter(md)
        name_ok = fm.get("name") == d.name
        desc_ok = len(fm.get("description", "")) >= 20
        record(
            "skills", name_ok, f"{md.relative_to(ROOT)} frontmatter name == '{d.name}'"
        )
        record("skills", desc_ok, f"{md.relative_to(ROOT)} has a description")
        names.append(d.name)
    cmds = ROOT / ".claude" / "commands"
    if cmds.exists():
        for md in sorted(cmds.glob("*.md")):
            fm = frontmatter(md)
            record(
                "skills",
                bool(fm.get("description")),
                f"{md.relative_to(ROOT)} has a description",
            )
            names.append(md.stem)
    return names


def check_symlinks() -> None:
    oc = ROOT / ".opencode" / "skills"
    cl = ROOT / ".claude" / "skills"
    if not oc.exists():
        return
    oc_names = set()
    for p in sorted(oc.iterdir()):
        oc_names.add(p.name)
        if p.is_symlink():
            record(
                "symlinks",
                p.exists(),
                f"{p.relative_to(ROOT)} -> {os.readlink(p)} resolves",
            )
        else:
            record(
                "symlinks",
                (p / "SKILL.md").exists(),
                f"{p.relative_to(ROOT)}/SKILL.md exists",
            )
    if cl.exists():
        cl_names = {p.name for p in cl.iterdir() if p.is_dir()}
        missing = sorted(cl_names - oc_names)
        extra = sorted(oc_names - cl_names)
        record(
            "symlinks",
            not missing,
            ".opencode/skills has every .claude skill"
            + (f" (missing: {', '.join(missing)})" if missing else ""),
        )
        record(
            "symlinks",
            not extra,
            ".claude/skills has every .opencode skill"
            + (f" (missing: {', '.join(extra)})" if extra else ""),
        )


PATH_RE = re.compile(
    r"`([A-Za-z0-9_./-]+/[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,5})(?::\d+(?:-\d+)?)?`"
)


def check_agents_md(
    max_kb: float, skill_names: list[str], ignore_paths: list[str]
) -> None:
    md = ROOT / "AGENTS.md"
    if not md.exists():
        record("agents-md", False, "AGENTS.md missing")
        return
    size_kb = md.stat().st_size / 1024
    record(
        "agents-md",
        size_kb <= max_kb,
        f"AGENTS.md is {size_kb:.1f} KB (limit {max_kb} KB)",
    )
    text = md.read_text(encoding="utf-8", errors="replace")
    for name in skill_names:
        record("agents-md", name in text, f"AGENTS.md mentions skill '{name}'")
    claude_md = ROOT / "CLAUDE.md"
    if claude_md.exists():
        record(
            "agents-md",
            "@AGENTS.md" in claude_md.read_text(),
            "CLAUDE.md imports @AGENTS.md",
        )
    # Paths mentioned in AGENTS.md must exist (generated/ignored paths are skipped).
    seen = set()
    for m in PATH_RE.finditer(text):
        tok = m.group(1)
        if (
            tok in seen
            or "*" in tok
            or "<" in tok
            or tok.startswith(("http", "~", "/"))
        ):
            continue
        seen.add(tok)
        if tok in ignore_paths:
            continue
        top = tok.split("/")[0]
        if top in GENERATED_TREES and not (ROOT / tok).exists():
            continue  # generated or git-ignored tree
        record("paths", (ROOT / tok).exists(), f"AGENTS.md path exists: {tok}")


GENERATED_TREES = {
    "exports",
    "data",
    "output",
    "logs",
    "dist",
    ".tdgl3d-run",
    "node_modules",
    "release",
}


def check_stale() -> None:
    p = ROOT / ".github" / "copilot-instructions.md"
    if not p.exists():
        record("stale", True, ".github/copilot-instructions.md absent")
        return
    text = p.read_text().strip()
    ok = len(text) < 300 and "AGENTS.md" in text
    record(
        "stale",
        ok,
        (
            ".github/copilot-instructions.md is a short pointer to AGENTS.md"
            if ok
            else ".github/copilot-instructions.md is a stale standalone file"
        ),
    )


def check_commands(cmds: list[str]) -> None:
    for c in cmds:
        r = subprocess.run(c, shell=True, cwd=ROOT, capture_output=True, text=True)
        tail = (r.stdout + r.stderr).strip().splitlines()[-1:] if r.returncode else []
        detail = f" — {tail[0][:120]}" if tail else ""
        record("commands", r.returncode == 0, f"`{c}` exit {r.returncode}{detail}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--max-agents-kb", type=float, default=12.0)
    ap.add_argument("--require-deny", action="append", default=[])
    ap.add_argument("--require-allow", action="append", default=[])
    ap.add_argument(
        "--run", action="append", default=[], help="command that must exit 0"
    )
    ap.add_argument(
        "--ignore-path",
        action="append",
        default=[],
        help="AGENTS.md path token that is a placeholder, gitignored or elsewhere",
    )
    args = ap.parse_args()

    registered = check_settings(args.require_deny, args.require_allow)
    check_hooks(registered)
    names = check_skills()
    check_symlinks()
    check_agents_md(args.max_agents_kb, names, args.ignore_path)
    check_stale()
    check_commands(args.run)

    failed = 0
    for group, ok, msg in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  [{group:9}] {msg}")
        failed += 0 if ok else 1
    print(f"\n{len(RESULTS) - failed}/{len(RESULTS)} checks passed")
    return failed


if __name__ == "__main__":
    sys.exit(main())
