"""Adds the author of a "Join the leaderboard" issue to students.csv.

Run by .github/workflows/join.yml. Inputs come from environment variables:
  LOGIN  - the issue author's GitHub username (set by GitHub, can't be faked)
  BODY   - the issue text from the join form
Writes the reply to post on the issue to reply.md, and prints "added",
"updated" or "invalid" to result.txt.
"""
import csv
import os
import re

login = os.environ["LOGIN"].strip()
body = os.environ.get("BODY", "")


def field(label):
    """Read one answer from a GitHub issue form body."""
    m = re.search(rf"###\s*{re.escape(label)}\s*\n+(.*?)(?=\n###|\Z)", body, re.S)
    value = (m.group(1).strip() if m else "")
    return "" if value == "_No response_" else value


# Clean the name: one line, no commas or quotes, sensible length.
name = re.sub(r"[\r\n,\"<>]", " ", field("Your full name"))
name = re.sub(r"\s+", " ", name).strip()[:60] or login

repo = field("Assignment repo (optional)").strip().removeprefix("https://github.com/").strip("/")
problem = None
if repo and not re.fullmatch(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}", repo):
    problem = (f"The assignment repo `{repo[:120]}` doesn't look like `owner/repo-name`. "
               "Please open a new join request with the correct repo, or leave it empty.")

if problem:
    open("result.txt", "w").write("invalid")
    open("reply.md", "w").write(f"Sorry @{login}, I couldn't add you. {problem}")
    raise SystemExit(0)

with open("students.csv", newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

existing = next((r for r in rows if r["github"].strip().lower() == login.lower()), None)
if existing:
    existing["name"], existing["repo"] = name, repo
    result = "updated"
else:
    rows.append({"name": name, "github": login, "repo": repo})
    result = "added"

with open("students.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["name", "github", "repo"], lineterminator="\n")
    w.writeheader()
    w.writerows(rows)

where = f"commits in `{repo}`" if repo else "commits in your public repos"
verb = "You're on the leaderboard" if result == "added" else "Your details are updated"
open("result.txt", "w").write(result)
open("reply.md", "w").write(
    f"{verb}, @{login}! Name: **{name}**. Counting {where}.\n\n"
    "Your stats will appear within a few minutes. Make sure the email in your git settings "
    "is added to your GitHub account (Settings → Emails), or your commits won't count.")
print(result, login, name, repo)
