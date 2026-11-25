"""Adds students from "Join the leaderboard" issues to students.csv and data.json.

Run by .github/workflows/join.yml.
- When a student opens a join issue, only that issue is handled.
- When the teacher clicks "Run workflow", every open join issue is handled
  (useful for requests that got stuck).

Usernames come from the issue author's account, so nobody can add someone else.
Writes replies.json: the message to post on each issue before closing it.
Does not commit or push; the workflow does that.
"""
import csv
import json
import os
import re
import subprocess

import update

REPO = os.environ["GITHUB_REPOSITORY"]
NEEDS_APPROVAL = os.environ.get("REQUIRE_APPROVAL", "").lower() == "true"


def issues_to_handle():
    """Return a list of {number, login, body, labels} for the join issues to process."""
    if os.environ.get("GITHUB_EVENT_NAME") == "issues":
        with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
            issue = json.load(f)["issue"]
        return [{"number": issue["number"], "login": issue["user"]["login"], "body": issue.get("body") or "",
                 "labels": [l["name"] for l in issue.get("labels", [])]}]
    out = subprocess.run(["gh", "issue", "list", "--repo", REPO, "--state", "open", "--limit", "500",
                          "--json", "number,title,body,author,labels"],
                         check=True, capture_output=True, text=True).stdout
    found = []
    for i in json.loads(out):
        if not i["title"].strip().lower().startswith("join"):
            continue
        labels = [l["name"] for l in i.get("labels", [])]
        if NEEDS_APPROVAL and "approved" not in labels:
            continue
        found.append({"number": i["number"], "login": i["author"]["login"], "body": i.get("body") or "",
                      "labels": labels})
    return sorted(found, key=lambda i: i["number"])


def field(body, label):
    """Read one answer from a GitHub issue form body."""
    m = re.search(rf"###\s*{re.escape(label)}\s*\n+(.*?)(?=\n###|\Z)", body, re.S)
    value = m.group(1).strip() if m else ""
    return "" if value == "_No response_" else value


def apply(rows, login, body):
    """Add or update one student in rows. Returns (ok, reply)."""
    name = re.sub(r"[\r\n,\"<>]", " ", field(body, "Your full name"))
    name = re.sub(r"\s+", " ", name).strip()[:60] or login
    repo = field(body, "Assignment repo (optional)").strip().removeprefix("https://github.com/").strip("/")
    if repo and not re.fullmatch(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}", repo):
        return False, (f"Sorry @{login}, I couldn't add you. The assignment repo `{repo[:120]}` doesn't look like "
                       "`owner/repo-name`. Please open a new join request with the correct repo, or leave it empty.")

    existing = next((r for r in rows if r["github"].strip().lower() == login.lower()), None)
    if existing:
        existing["name"], existing["repo"] = name, repo
        verb = "Your details are updated"
    else:
        rows.append({"name": name, "github": login, "repo": repo})
        verb = "You're on the leaderboard"
    where = f"commits in `{repo}`" if repo else "commits in your public repos"
    return True, (f"{verb}, @{login}! Name: **{name}**. Counting {where}.\n\n"
                  "Your stats are on the leaderboard now (the page can take 1–2 minutes to refresh). "
                  "Make sure the email in your git settings is added to your GitHub account "
                  "(Settings → Emails), or your commits won't count.")


def main():
    issues = issues_to_handle()
    print(f"{len(issues)} join request(s) to handle")
    with open("students.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    replies, joined = [], []
    for i in issues:
        ok, reply = apply(rows, i["login"], i["body"])
        replies.append({"number": i["number"], "reply": reply})
        if ok:
            joined.append(i["login"])
        print(f"#{i['number']} {i['login']}: {'ok' if ok else 'invalid'}")

    with open("students.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "github", "repo"], lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    if joined:
        update.update_only(dict.fromkeys(joined))  # fetch stats for just these students
    with open("replies.json", "w", encoding="utf-8") as f:
        json.dump(replies, f)


if __name__ == "__main__":
    main()
