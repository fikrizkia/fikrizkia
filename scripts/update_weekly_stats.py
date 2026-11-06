#!/usr/bin/env python3
"""
Script otomatis untuk mengambil statistik commit mingguan (Senin - Minggu)
berdasarkan zona waktu WIB (UTC+7) dan memperbarui bagian WEEKLY-ACTIVITY di README.md.
"""

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

USERNAME = os.environ.get("GITHUB_USERNAME", "fikrizkia")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
README_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md")

WIB = timezone(timedelta(hours=7))
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

START_MARKER = "<!--START_SECTION:weekly_activity-->"
END_MARKER = "<!--END_SECTION:weekly_activity-->"


def github_request(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-readme-stats-updater",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_repos():
    repos = []
    page = 1
    while True:
        if TOKEN:
            url = f"https://api.github.com/user/repos?per_page=100&page={page}&affiliation=owner,collaborator"
        else:
            url = f"https://api.github.com/users/{USERNAME}/repos?per_page=100&page={page}&type=owner"

        try:
            data = github_request(url)
        except urllib.error.HTTPError:
            url = f"https://api.github.com/users/{USERNAME}/repos?per_page=100&page={page}&type=owner"
            data = github_request(url)

        if not data:
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1
    return repos


def fetch_weekly_commits():
    repos = fetch_repos()
    days_count = [0] * 7
    seen_shas = set()

    for repo in repos:
        if repo.get("fork"):
            continue
        full_name = repo.get("full_name", f"{USERNAME}/{repo['name']}")
        page = 1
        while True:
            url = f"https://api.github.com/repos/{full_name}/commits?per_page=100&page={page}"
            try:
                commits = github_request(url)
            except Exception:
                break

            if not commits or not isinstance(commits, list):
                break

            for c in commits:
                sha = c.get("sha")
                if not sha or sha in seen_shas:
                    continue

                author_login = ((c.get("author") or {}).get("login") or "").lower()
                commit_author = ((c.get("commit") or {}).get("author") or {})
                author_name = (commit_author.get("name") or "").lower()
                author_email = (commit_author.get("email") or "").lower()

                if (
                    author_login == USERNAME.lower()
                    or "fikri" in author_name
                    or USERNAME.lower() in author_name
                    or USERNAME.lower() in author_email
                ):
                    date_str = commit_author.get("date")
                    if date_str:
                        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00")).astimezone(WIB)
                        days_count[dt.weekday()] += 1
                        seen_shas.add(sha)

            if len(commits) < 100:
                break
            page += 1

    return days_count


def build_markdown_table(days_count):
    total = sum(days_count)
    if total == 0:
        max_idx = 4  # Default Friday
    else:
        max_idx = max(range(7), key=lambda i: days_count[i])

    most_productive_day = DAY_NAMES[max_idx]

    lines = [
        START_MARKER,
        f"##### 📅 I'm Most Productive on {most_productive_day} — Aktivitas Mingguan",
        "",
        "| Hari | Total Commits | Persentase Aktivitas |",
        "| :--- | :---: | :---: |",
    ]

    for i, day_name in enumerate(DAY_NAMES):
        count = days_count[i]
        pct = (count / total * 100) if total > 0 else 0.0
        commit_label = "commit" if count == 1 else "commits"
        if i == max_idx and total > 0:
            pct_str = f"**{pct:.2f} %** 🚀"
        else:
            pct_str = f"`{pct:.2f} %`"
        lines.append(f"| **{day_name}** | {count} {commit_label} | {pct_str} |")

    lines.append(END_MARKER)
    return "\n".join(lines)


def update_readme():
    days_count = fetch_weekly_commits()
    new_section = build_markdown_table(days_count)

    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(
        rf"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}",
        re.DOTALL,
    )

    if pattern.search(content):
        updated_content = pattern.sub(new_section, content)
    else:
        raise RuntimeError(f"Marker {START_MARKER} tidak ditemukan di README.md")

    if updated_content != content:
        with open(README_PATH, "w", encoding="utf-8") as f:
            f.write(updated_content)
        print("README.md berhasil diperbarui dengan statistik mingguan terbaru!")
    else:
        print("Statistik mingguan di README.md sudah paling baru (tidak ada perubahan).")


if __name__ == "__main__":
    update_readme()
