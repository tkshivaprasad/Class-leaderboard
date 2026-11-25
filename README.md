# Class Leaderboard

A free leaderboard that tracks your students' GitHub commits. It runs entirely on GitHub, so there is no server to manage.

- **GitHub Actions** runs `update.py` every 6 hours and saves the results to `data.json`.
- **GitHub Pages** serves `index.html`, which shows the ranking.

## Setup (about 10 minutes)

1. **Create a repo.** Make a new repository on GitHub (for example `class-leaderboard`) and upload every file in this folder, including the `.github` folder.
   - Tip: the `.github` folder is hidden on Mac/Linux. You can also create `.github/workflows/update.yml` with GitHub's "Add file → Create new file" and paste in its contents.
2. **Add your students.** Edit `students.csv`, with one row per student:
   ```
   name,github,repo
   Aarav Sharma,aarav-sharma,
   Diya Patel,diyapatel,diyapatel/python-assignments
   ```
   - Leave `repo` empty to count commits across all of the student's **public** repos.
   - Set `repo` to `owner/repo-name` to count commits in **one assignment repo** only.
3. **Allow the workflow to save data.** Go to Settings → Actions → General → Workflow permissions, choose **Read and write permissions**, and click Save.
4. **Turn on Pages.** Go to Settings → Pages, set Source to **Deploy from a branch**, pick `main` and `/ (root)`, and click Save.
5. **Run it once.** On the Actions tab, open **Update leaderboard** and click **Run workflow**.

Your leaderboard will be at `https://<your-username>.github.io/class-leaderboard/`.

## Private repos

The built-in token can only read public repos. If students work in private repos:
1. Create a fine-grained personal access token (Settings → Developer settings → Personal access tokens) that can read those repos, for example a token on a GitHub organization or Classroom that owns them.
2. In the leaderboard repo, go to Settings → Secrets and variables → Actions and add it as `LEADERBOARD_TOKEN`.

Commit search (empty `repo`) only ever sees public commits. Use the `repo` column for private work.

## Scoring

The rules are at the top of `update.py`. By default:

| Rule | Points |
|---|---|
| Each commit (counting at most 10 a day, so spam doesn't pay) | 1 |
| Each day with at least one commit | 5 |
| Each day in the current streak of consecutive days | 3 |

Change the numbers to suit your class. The leaderboard footer updates to match.

## Using the page

- Click any column header to sort.
- **Needs attention** shows students with no commits in the last 7 days.
- The bar strip shows commits per day over the last 30 days.

## Notes

- Commits count only if the student's git email is linked to their GitHub account. If a student shows 0 commits but has pushed work, ask them to add their commit email under GitHub Settings → Emails.
- The `data.json` included here is sample data. It is replaced on the first run.
