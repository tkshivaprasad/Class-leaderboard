"""Collects each student's GitHub activity and writes data.json for the leaderboard.

Reads students.csv with these columns:
  name    - display name
  github  - GitHub username
  repo    - optional "owner/repo". If empty, the student's CLASS_REPO is used
            (e.g. aarav-sharma/class-programs).

Only commits in that one repo count, and the repo must be public.

Needs a GITHUB_TOKEN environment variable. Inside GitHub Actions it is
provided automatically. Uses only the Python standard library.
"""
import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

DAYS = 30  # how far back to look

# Every student keeps their programs in a public repo with this name.
# Set it to "" to count commits in all of a student's public repos instead.
CLASS_REPO = "class-programs"

# File types counted as programs in the "Programs" column.
PROGRAM_EXTS = {".py", ".c", ".cpp", ".cc", ".h", ".hpp", ".java", ".js", ".ts", ".jsx", ".tsx",
                ".html", ".css", ".php", ".rb", ".go", ".rs", ".kt", ".swift", ".cs", ".r", ".sql",
                ".sh", ".dart", ".m", ".scala", ".pl", ".lua", ".ipynb"}

# Scoring rules: change these to suit your class.
POINTS_PER_COMMIT = 1
POINTS_PER_ACTIVE_DAY = 5   # rewards working regularly, not just commit spam
POINTS_PER_STREAK_DAY = 3   # current run of consecutive days with commits
MAX_COMMITS_PER_DAY = 10    # commits above this on one day earn nothing

TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com"


def get(url):
    """GET a GitHub API URL and return the parsed JSON, waiting out rate limits."""
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "class-leaderboard",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and attempt < 3:
                reset = e.headers.get("X-RateLimit-Reset")
                wait = max(5, int(reset) - int(time.time()) + 1) if reset else 30
                print(f"  rate limited, waiting {min(wait, 120)}s")
                time.sleep(min(wait, 120))
                continue
            if e.code in (404, 409, 422):
                return None  # unknown user or repo, or an empty repo
            raise
    return None


def repo_of(student):
    """The repo to track for this student, or "" to search all their public repos."""
    repo = (student.get("repo") or "").strip()
    if repo:
        return repo
    return f"{student['github'].strip()}/{CLASS_REPO}" if CLASS_REPO else ""


def commit_dates(student, since, repo):
    """Return a list of commit dates (UTC) for this student since `since`."""
    user = student["github"].strip()
    dates = []
    if repo:
        params = {"since": since.isoformat(), "per_page": 100}
        # In the student's own repo every commit is theirs (this also counts commits made
        # with an email that isn't linked to their account). In someone else's repo,
        # only count the student's own commits.
        if repo.split("/")[0].lower() != user.lower():
            params["author"] = user
        for page in range(1, 11):
            q = urllib.parse.urlencode({**params, "page": page})
            items = get(f"{API}/repos/{repo}/commits?{q}") or []
            dates += [i["commit"]["author"]["date"] for i in items]
            if len(items) < 100:
                break
    else:
        # Commits across all the student's public repos, via commit search.
        for page in range(1, 6):
            q = urllib.parse.urlencode({
                "q": f"author:{user} author-date:>={since.date().isoformat()}",
                "sort": "author-date", "order": "desc", "per_page": 100, "page": page})
            res = get(f"{API}/search/commits?{q}")
            items = (res or {}).get("items", [])
            dates += [i["commit"]["author"]["date"] for i in items]
            time.sleep(2.1)  # search API allows 30 requests a minute
            if len(items) < 100:
                break
    return [datetime.fromisoformat(d.replace("Z", "+00:00")).astimezone(timezone.utc).date()
            for d in dates]


def count_programs(info):
    """Count program files in the default branch of the repo."""
    tree = get(f"{API}/repos/{info['full_name']}/git/trees/{urllib.parse.quote(info['default_branch'])}?recursive=1")
    files = [t["path"] for t in (tree or {}).get("tree", []) if t.get("type") == "blob"]
    return sum(1 for f in files if os.path.splitext(f)[1].lower() in PROGRAM_EXTS)


def summarise(student, today):
    since = datetime.combine(today - timedelta(days=DAYS - 1), datetime.min.time(), timezone.utc)
    repo, programs = repo_of(student), None
    if repo:
        info = get(f"{API}/repos/{repo}")
        if not info or info.get("private"):
            # Repo doesn't exist yet, is private, or the name is wrong.
            return {"name": student["name"].strip(), "github": student["github"].strip(), "repo": repo,
                    "status": "no_repo", "score": 0, "commits_30d": 0, "commits_7d": 0, "active_days": 0,
                    "streak": 0, "programs": 0, "last_commit": None, "daily": [0] * DAYS}
        repo = info["full_name"]  # correct capitalisation
        programs = count_programs(info)
    days = commit_dates(student, since, repo)
    daily = [0] * DAYS  # oldest first
    for d in days:
        i = (d - since.date()).days
        if 0 <= i < DAYS:
            daily[i] += 1

    streak = 0
    # A streak still counts if the student hasn't committed yet today.
    start = DAYS - 1 if daily[-1] else DAYS - 2
    for i in range(start, -1, -1):
        if not daily[i]:
            break
        streak += 1

    commits = sum(daily)
    counted = sum(min(c, MAX_COMMITS_PER_DAY) for c in daily)
    active = sum(1 for c in daily if c)
    score = (counted * POINTS_PER_COMMIT + active * POINTS_PER_ACTIVE_DAY
             + streak * POINTS_PER_STREAK_DAY)
    return {
        "name": student["name"].strip(),
        "github": student["github"].strip(),
        "repo": repo,
        "status": "ok",
        "programs": programs,
        "score": score,
        "commits_30d": commits,
        "commits_7d": sum(daily[-7:]),
        "active_days": active,
        "streak": streak,
        "last_commit": max(days).isoformat() if days else None,
        "daily": daily,
    }


def save(rows, today):
    rows.sort(key=lambda r: r.get("score", -1), reverse=True)
    out = {
        "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "days": DAYS,
        "window_start": (today - timedelta(days=DAYS - 1)).isoformat(),
        "class_repo": CLASS_REPO,
        "scoring": {"commit": POINTS_PER_COMMIT, "active_day": POINTS_PER_ACTIVE_DAY,
                    "streak_day": POINTS_PER_STREAK_DAY, "max_commits_per_day": MAX_COMMITS_PER_DAY},
        "students": rows,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)


def load_students():
    with open("students.csv", newline="", encoding="utf-8") as f:
        return [s for s in csv.DictReader(f) if (s.get("github") or "").strip()]


def load_rows():
    try:
        with open("data.json", encoding="utf-8") as f:
            data = json.load(f)
        return [] if data.get("sample") else [r for r in data.get("students", []) if r.get("github")]
    except (OSError, ValueError):
        return []


def safe_summary(s, today):
    print(f"Fetching {s['github']} ...")
    try:
        return summarise(s, today)
    except Exception as e:  # one broken entry should not stop the whole run
        print(f"  failed: {e}")
        return {"name": s["name"], "github": s["github"], "error": str(e)}


def merge(new_rows):
    """Put new_rows into data.json, keeping everyone else's existing stats.
    Students no longer in students.csv are dropped."""
    today = datetime.now(timezone.utc).date()
    current = {s["github"].strip().lower(): s for s in load_students()}
    by_user = {r["github"].lower(): r for r in load_rows()}
    for r in new_rows:
        by_user[r["github"].lower()] = r
    rows = []
    for login, r in by_user.items():
        if login in current:
            r["name"] = current[login]["name"].strip()  # pick up name changes
            rows.append(r)
    save(rows, today)


def update_only(logins):
    """Fetch stats for just these students (used when someone joins)."""
    today = datetime.now(timezone.utc).date()
    wanted = {l.lower() for l in logins}
    merge([safe_summary(s, today) for s in load_students() if s["github"].strip().lower() in wanted])


def main():
    today = datetime.now(timezone.utc).date()
    rows = [safe_summary(s, today) for s in load_students()]
    save(rows, today)
    with open("/tmp/leaderboard_rows.json", "w") as f:  # kept so a retry can re-merge
        json.dump(rows, f)
    print(f"Wrote data.json with {len(rows)} students")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "--merge":
        # Re-apply a full run's results on top of a newer data.json without re-fetching.
        merge(json.load(open(sys.argv[2])))
    else:
        main()
