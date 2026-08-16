#!/usr/bin/env python3
"""Checks official SG voucher-scheme pages for content changes.

Compares each page's visible text (script/style stripped, whitespace normalised) against a
snapshot stored in .github/source-snapshots/. On a difference, sets GITHUB_OUTPUT so the
workflow can open/update a GitHub Issue for manual review -- this script never edits
index.html's TRANCHES data itself.

Caveat: government press announcements have historically preceded these microsites being
updated (e.g. the Jan 2027 CDC tranche was reported by news outlets on 29 Jul 2026 while
vouchers.cdc.gov.sg's own newsroom page still didn't mention it weeks later). "No change
detected" means no change to these specific pages, not "no new voucher announced anywhere" --
a human still needs to skim the news occasionally, this just catches the common case.
"""
import os
import re
import urllib.request

SOURCES = {
    "CDC Vouchers homepage": "https://vouchers.cdc.gov.sg/",
    "CDC Vouchers newsroom": "https://vouchers.cdc.gov.sg/about/newsroom/",
    "SG60 Vouchers homepage": "https://vouchers.sg60.gov.sg/",
    "Climate Vouchers homepage": "https://www.climate-friendly-households.gov.sg/",
}

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "source-snapshots")


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (voucher-source-watcher; +github-actions)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def main():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    changed, failed, summary_lines = [], [], []

    for name, url in SOURCES.items():
        path = os.path.join(SNAPSHOT_DIR, slug(name) + ".txt")

        try:
            new_text = fetch_text(url)
        except Exception as e:
            failed.append(name)
            summary_lines.append(f"- **{name}** ({url}): fetch failed — `{e}`")
            continue

        old_text = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                old_text = f.read()

        if old_text and old_text != new_text:
            changed.append(name)
            summary_lines.append(f"- **{name}** ({url}): content changed since last check")
        elif not old_text:
            summary_lines.append(f"- **{name}** ({url}): first run, baseline snapshot saved")
        else:
            summary_lines.append(f"- **{name}** ({url}): no change")

        with open(path, "w", encoding="utf-8") as f:
            f.write(new_text)

    triggered = changed or failed
    summary = "\n".join(summary_lines)
    print(summary)
    if triggered:
        print(f"\nNeeds attention: {', '.join(changed + [f'{n} (fetch failed)' for n in failed])}")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"triggered={'true' if triggered else 'false'}\n")
            f.write(f"changed_sites={', '.join(changed) or 'none'}\n")
            f.write(f"failed_sites={', '.join(failed) or 'none'}\n")
            f.write(f"summary<<EOF\n{summary}\nEOF\n")


if __name__ == "__main__":
    main()
