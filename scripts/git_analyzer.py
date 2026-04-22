#!/usr/bin/env python3
"""
git_analyzer.py
---------------
Analyzes git commit history for the current repository.
Groups commits by author, shows per-commit details, cumulative stats,
and exports a JSON report.

Usage:
    python git_analyzer.py              # analyze current repo
    python git_analyzer.py --include-merges  # include merge commits
    python git_analyzer.py --output report.json  # custom output filename
"""

import subprocess
import json
import argparse
import sys
from collections import defaultdict
from datetime import datetime

# pyright: reportPossiblyUnboundVariable=false, reportGeneralTypeIssues=false, reportAttributeAccessIssue=false, reportOperatorIssue=false, reportOptionalMemberAccess=false, reportArgumentType=false

# ── Identity Mapping ───────────────────────────────────────────────────────────
# Groups multiple author identities that belong to the same person.
IDENTITY_GROUPS = [
    {
        "name": "David Wong",
        "identities": ["davidwong666", "DavidWongLinux", "davidwkk"],
    },
    {"name": "Peng Minqi", "identities": ["mencare", "mencaire", "Peng Minqi"]},
]


def _merge_identities(author_map: dict) -> tuple[dict, list[dict]]:
    """
    Merge identity groups into combined author entries.
    Returns (merged_map, abstract) where abstract contains the combined stats.
    """
    identity_to_group: dict[str, str] = {}
    for group in IDENTITY_GROUPS:
        for ident in group["identities"]:
            identity_to_group[ident.lower()] = group["name"]

    merged: dict = {}
    abstract: list[dict] = []

    for author, data in author_map.items():
        group_name = identity_to_group.get(author.lower())
        if group_name:
            if group_name not in merged:
                merged[group_name] = {
                    "email": data["email"],
                    "total_commits": 0,
                    "total_additions": 0,
                    "total_deletions": 0,
                    "total_files_changed": 0,
                    "first_commit": data["first_commit"],
                    "last_commit": data["last_commit"],
                    "commits": [],
                    "identities": [],
                }
            merged[group_name]["identities"].append(author)
            merged[group_name]["total_commits"] += data["total_commits"]
            merged[group_name]["total_additions"] += data["total_additions"]
            merged[group_name]["total_deletions"] += data["total_deletions"]
            merged[group_name]["total_files_changed"] += data["total_files_changed"]
            merged[group_name]["commits"].extend(data["commits"])

            if data["first_commit"]:
                if (
                    merged[group_name]["first_commit"] is None
                    or data["first_commit"] < merged[group_name]["first_commit"]
                ):
                    merged[group_name]["first_commit"] = data["first_commit"]
            if data["last_commit"]:
                if data["last_commit"] > merged[group_name]["last_commit"]:
                    merged[group_name]["last_commit"] = data["last_commit"]
        else:
            merged[author] = data

    for group in IDENTITY_GROUPS:
        if group["name"] in merged:
            abstract.append({"name": group["name"], **merged[group["name"]]})

    # Add non-merged authors to abstract
    for author, data in merged.items():
        if author not in [g["name"] for g in IDENTITY_GROUPS]:
            abstract.append({"name": author, **data})

    return merged, abstract


# ── ANSI Colors ───────────────────────────────────────────────────────────────
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    DIM = "\033[2m"


def colorize(text, *codes):
    return "".join(codes) + str(text) + C.RESET


# ── Git Helpers ───────────────────────────────────────────────────────────────
def run_git(*args):
    """Run a git command and return stdout lines."""
    result = subprocess.run(["git"] + list(args), capture_output=True, text=True)
    if result.returncode != 0:
        print(colorize(f"[ERROR] git command failed: git {' '.join(args)}", C.RED))
        print(colorize(result.stderr.strip(), C.RED))
        sys.exit(1)
    return result.stdout.strip()


def check_git_repo():
    """Ensure we're inside a git repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True
    )
    if result.returncode != 0:
        print(colorize("[ERROR] Not inside a git repository.", C.RED))
        sys.exit(1)


def get_repo_name():
    path = run_git("rev-parse", "--show-toplevel")
    return path.split("/")[-1]


def get_current_branch():
    return run_git("rev-parse", "--abbrev-ref", "HEAD")


# ── Commit Parsing ────────────────────────────────────────────────────────────
SEPARATOR = "||GIT_SEP||"


def fetch_commits(include_merges: bool) -> list[dict]:
    """
    Fetch all commits with metadata.
    Format: hash|author_name|author_email|date_iso|subject
    """
    fmt = SEPARATOR.join(["%H", "%an", "%ae", "%aI", "%s"])
    args = ["log", f"--format={fmt}"]
    if not include_merges:
        args.append("--no-merges")

    raw = run_git(*args)
    if not raw:
        return []

    commits = []
    for line in raw.splitlines():
        parts = line.split(SEPARATOR)
        if len(parts) != 5:
            continue
        hash_, name, email, date_iso, subject = parts
        commits.append(
            {
                "hash": hash_,
                "short_hash": hash_[:7],
                "author": name.strip(),
                "email": email.strip(),
                "date": date_iso.strip(),
                "subject": subject.strip(),
            }
        )
    return commits


def fetch_diff_stats(commit_hash: str) -> tuple[int, int, int]:
    """
    Returns (additions, deletions, files_changed) for a given commit.
    Uses --numstat for accuracy.
    """
    raw = run_git("show", "--numstat", "--format=", commit_hash)
    additions, deletions, files = 0, 0, 0
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            try:
                additions += int(parts[0]) if parts[0] != "-" else 0
                deletions += int(parts[1]) if parts[1] != "-" else 0
                files += 1
            except ValueError:
                continue
    return additions, deletions, files


def _compute_file_stats(commits: list[dict]) -> dict:
    """Compute aggregate file stats across all commits."""
    backend_files = set()
    frontend_files = set()
    migration_files = set()
    total_files = set()

    for commit in commits:
        raw = run_git("show", "--numstat", "--format=", commit["hash"])
        for line in raw.splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                filepath = parts[2]
                total_files.add(filepath)
                if filepath.startswith("backend/"):
                    backend_files.add(filepath)
                elif filepath.startswith("frontend/") or "/src/" in filepath:
                    frontend_files.add(filepath)

    # Detect migrations via alembic/versions path in file tree
    migration_result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
    )
    for line in migration_result.stdout.splitlines():
        if "alembic/versions/" in line or "migrations/" in line:
            migration_files.add(line)

    return {
        "total_files": len(total_files),
        "backend_files": len(backend_files),
        "frontend_files": len(frontend_files),
        "db_migrations": len(migration_files),
    }


# ── Data Aggregation ──────────────────────────────────────────────────────────
def build_author_map(commits: list[dict]) -> dict:
    """
    Groups commits by author and computes cumulative stats.
    Returns a dict keyed by author name.
    """
    authors = defaultdict(
        lambda: {
            "email": "",
            "commits": [],
            "total_commits": 0,
            "total_additions": 0,
            "total_deletions": 0,
            "total_files_changed": 0,
            "first_commit": None,
            "last_commit": None,
        }
    )

    total = len(commits)
    for i, commit in enumerate(commits):
        print(
            colorize(
                f"\r  Fetching diff stats [{i + 1}/{total}] {commit['short_hash']} ...",
                C.DIM,
            ),
            end="",
            flush=True,
        )

        adds, dels, files = fetch_diff_stats(commit["hash"])
        commit["additions"] = adds
        commit["deletions"] = dels
        commit["files_changed"] = files
        commit["net_lines"] = adds - dels

        author = commit["author"]
        a = authors[author]
        a["email"] = commit["email"]
        a["commits"].append(commit)
        a["total_commits"] += 1
        a["total_additions"] += adds
        a["total_deletions"] += dels
        a["total_files_changed"] += files

        dt = datetime.fromisoformat(commit["date"])
        if a["first_commit"] is None or dt < datetime.fromisoformat(a["first_commit"]):
            a["first_commit"] = commit["date"]
        if a["last_commit"] is None or dt > datetime.fromisoformat(a["last_commit"]):
            a["last_commit"] = commit["date"]

    print()  # newline after progress
    return dict(authors)


# ── Terminal Output ───────────────────────────────────────────────────────────
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


def fmt_date(iso: str) -> str:
    dt = datetime.fromisoformat(iso)
    return (
        f"{dt.day:02d} {MONTHS[dt.month - 1]} {dt.year} {dt.hour:02d}:{dt.minute:02d}"
    )


def print_header(repo: str, branch: str, total_commits: int, include_merges: bool):
    width = 72
    print()
    print(colorize("═" * width, C.CYAN))
    print(colorize(f"  📦 Repo   : {repo}", C.BOLD + C.WHITE))
    print(colorize(f"  🌿 Branch : {branch}", C.BOLD + C.WHITE))
    print(
        colorize(
            f"  📝 Commits: {total_commits} ({'incl.' if include_merges else 'excl.'} merges)",
            C.BOLD + C.WHITE,
        )
    )
    print(
        colorize(
            f"  🕐 Run at : {datetime.now().strftime('%d %b %Y %H:%M:%S')}",
            C.BOLD + C.WHITE,
        )
    )
    print(colorize("═" * width, C.CYAN))
    print()


def print_author_section(author: str, data: dict, rank: int):
    width = 72
    net = data["total_additions"] - data["total_deletions"]
    net_str = f"+{net}" if net >= 0 else str(net)
    net_color = C.GREEN if net >= 0 else C.RED

    print(colorize(f"┌{'─' * (width - 2)}┐", C.BLUE))
    print(
        colorize(f"│  #{rank}  {author} <{data['email']}>", C.BOLD + C.YELLOW)
        + colorize(f"{'│':>{width - len(author) - len(data['email']) - 10}}", C.BLUE)
    )
    print(colorize(f"├{'─' * (width - 2)}┤", C.BLUE))

    # Summary row
    print(
        colorize("│  ", C.BLUE)
        + colorize(f"Commits: {data['total_commits']:<6}", C.WHITE)
        + colorize(f"  +{data['total_additions']:<7}", C.GREEN)
        + colorize(f"  -{data['total_deletions']:<7}", C.RED)
        + colorize(f"  Net: {net_str:<8}", net_color)
        + colorize(f"  Files Δ: {data['total_files_changed']}", C.CYAN)
        + colorize(f"{'│':>4}", C.BLUE)
    )
    print(
        colorize("│  ", C.BLUE)
        + colorize(f"First: {fmt_date(data['first_commit'])}", C.DIM)
        + colorize(f"   Last: {fmt_date(data['last_commit'])}", C.DIM)
        + colorize(f"{'│':>6}", C.BLUE)
    )
    print(colorize(f"├{'─' * (width - 2)}┤", C.BLUE))

    # Commit rows
    header = colorize(
        f"│  {'Hash':<8}  {'Date':<18}  {'Add':>6}  {'Del':>6}  {'Files':>5}  Subject",
        C.DIM,
    )
    print(header)
    print(colorize(f"│{'─' * (width - 2)}│", C.BLUE))

    for c in data["commits"]:
        dt_str = fmt_date(c["date"])
        subject = c["subject"][:35] + "…" if len(c["subject"]) > 35 else c["subject"]
        line = (
            colorize("│  ", C.BLUE)
            + colorize(f"{c['short_hash']}", C.MAGENTA)
            + f"  {dt_str:<18}  "
            + colorize(f"{'+' + str(c['additions']):>6}", C.GREEN)
            + colorize(f"  {'-' + str(c['deletions']):>6}", C.RED)
            + f"  {c['files_changed']:>5}  "
            + colorize(subject, C.WHITE)
        )
        print(line)

    print(colorize(f"└{'─' * (width - 2)}┘", C.BLUE))
    print()


def print_overall_summary(author_map: dict, file_stats: dict | None = None):
    total_commits = sum(d["total_commits"] for d in author_map.values())
    total_adds = sum(d["total_additions"] for d in author_map.values())
    total_dels = sum(d["total_deletions"] for d in author_map.values())
    total_files = sum(d["total_files_changed"] for d in author_map.values())
    net = total_adds - total_dels

    print(colorize("═" * 72, C.CYAN))
    print(colorize("  📊 OVERALL SUMMARY", C.BOLD + C.WHITE))
    print(colorize("═" * 72, C.CYAN))
    print(colorize(f"  Authors       : {len(author_map)}", C.WHITE))
    print(colorize(f"  Total Commits : {total_commits}", C.WHITE))
    print(colorize(f"  Total Additions: +{total_adds}", C.GREEN))
    print(colorize(f"  Total Deletions: -{total_dels}", C.RED))
    print(
        colorize(
            f"  Net Lines      : {'+' if net >= 0 else ''}{net}",
            C.GREEN if net >= 0 else C.RED,
        )
    )
    print(colorize(f"  Files Changed  : {total_files}", C.CYAN))
    if file_stats:
        print(colorize(f"  Backend Files  : {file_stats['backend_files']}", C.CYAN))
        print(colorize(f"  Frontend Files : {file_stats['frontend_files']}", C.CYAN))
        print(colorize(f"  DB Migrations : {file_stats['db_migrations']}", C.CYAN))
    print(colorize("═" * 72, C.CYAN))
    print()


# ── JSON Export ───────────────────────────────────────────────────────────────
def export_json(
    author_map: dict,
    repo: str,
    branch: str,
    output_file: str,
    abstract: list[dict],
    file_stats: dict,
):
    """Serialize the full report to a JSON file."""
    report = {
        "meta": {
            "repo": repo,
            "branch": branch,
            "generated": datetime.now().isoformat(),
        },
        "abstract": [
            {
                "name": a["name"],
                "identities": a.get("identities", []),
                "total_commits": a["total_commits"],
                "total_additions": a["total_additions"],
                "total_deletions": a["total_deletions"],
                "net_lines": a["total_additions"] - a["total_deletions"],
                "total_files_changed": a["total_files_changed"],
                "first_commit": a["first_commit"],
                "last_commit": a["last_commit"],
            }
            for a in abstract
        ],
        "file_stats": file_stats,
        "authors": {},
    }

    for author, data in author_map.items():
        report["authors"][author] = {
            "email": data["email"],
            "total_commits": data["total_commits"],
            "total_additions": data["total_additions"],
            "total_deletions": data["total_deletions"],
            "net_lines": data["total_additions"] - data["total_deletions"],
            "total_files_changed": data["total_files_changed"],
            "first_commit": data["first_commit"],
            "last_commit": data["last_commit"],
            "commits": [
                {
                    "hash": c["hash"],
                    "short_hash": c["short_hash"],
                    "date": c["date"],
                    "subject": c["subject"],
                    "additions": c["additions"],
                    "deletions": c["deletions"],
                    "files_changed": c["files_changed"],
                    "net_lines": c["net_lines"],
                }
                for c in data["commits"]
            ],
        }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(colorize(f"  💾 JSON report saved to {output_file}", C.GREEN))


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Analyze git commit history grouped by author."
    )
    parser.add_argument(
        "--include-merges",
        action="store_true",
        default=False,
        help="Include merge commits (excluded by default)",
    )
    parser.add_argument(
        "--output",
        default="git_report.json",
        help="Output JSON filename (default: git_report.json)",
    )
    args = parser.parse_args()

    # ── Validate ──
    check_git_repo()
    repo = get_repo_name()
    branch = get_current_branch()

    # ── Fetch ──
    print(colorize("\n  ⏳ Fetching commit log...", C.CYAN))
    commits = fetch_commits(include_merges=args.include_merges)

    if not commits:
        print(colorize("[INFO] No commits found.", C.YELLOW))
        sys.exit(0)

    # ── Diff Stats ──
    print(colorize(f"  ⏳ Loading diff stats for {len(commits)} commits...\n", C.CYAN))
    author_map = build_author_map(commits)

    # ── Merge Identities ──
    merged_map, abstract = _merge_identities(author_map)

    # ── File Stats ──
    file_stats = _compute_file_stats(commits)

    # Sort authors by total commits descending
    sorted_authors = sorted(
        merged_map.items(), key=lambda x: x[1]["total_commits"], reverse=True
    )

    # ── Print Terminal Report ──
    print_header(repo, branch, len(commits), args.include_merges)

    for rank, (author, data) in enumerate(sorted_authors, start=1):
        print_author_section(author, data, rank)

    print_overall_summary(merged_map, file_stats)

    # ── JSON Export ──
    export_json(merged_map, repo, branch, args.output, abstract, file_stats)


if __name__ == "__main__":
    main()
