    tracked = repo or (f"{login}/{update.CLASS_REPO}" if update.CLASS_REPO else "")
    if tracked:
        where = (f"The leaderboard tracks your repo **{tracked}**: "
                 f"https://github.com/{tracked}\n\n"
                 f"If you haven't made it yet, create a **public** repository named "
                 f"`{tracked.split('/')[1]}` and upload your programs there.")
    else:
        where = "The leaderboard counts commits in all your public repos."
    return True, (f"{verb}, @{login}! Name: **{name}**.\n\n{where}\n\n"
                  "Your stats are on the leaderboard now (the page can take 1–2 minutes to refresh).")
