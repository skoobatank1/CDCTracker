#!/usr/bin/env python3
"""Checks official SG voucher-scheme pages for content changes.

Stores each page's visible text (script/style stripped, whitespace normalised) as a snapshot in
.github/source-snapshots/, but only flags a change when the set of voucher "signals" differs --
scheme+year mentions, dollar amounts and dates (see SIGNAL_PATTERNS). Comparing raw text raised a
false alarm almost every week in Sep-Oct 2026 from template churn alone (footer "last updated"
dates, "(opens in new tab)" link labels, newsroom card elements reordered). On a signal change,
sets GITHUB_OUTPUT so the workflow can open/update a GitHub Issue for manual review -- this script
never edits index.html's TRANCHES data itself.

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

_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
SIGNAL_PATTERNS = [
    r"\b(?:CDC|SG60|Climate)\b[\w ]{0,30}?\b20\d\d\b(?: ?\([A-Za-z]+\))?",  # "CDC Vouchers Scheme 2026 (June)"
    r"\$ ?\d[\d,]*",                                                          # "$500"
    rf"\b\d{{1,2}} {_MONTH} 20\d\d\b",                                        # "31 Dec 2027"
    rf"\b{_MONTH} 20\d\d\b",                                                  # "January 2027"
]


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def normalise(text):
    # Isomer rewrites the footer's "last updated [on] <date>" on every site-wide redeploy -- strip it,
    # otherwise its date would register as a signal change.
    text = re.sub(r"last updated (?:on )?\d{1,2} \w+ \d{4}", "last updated", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def signals(text):
    text = normalise(text)
    return {m for p in SIGNAL_PATTERNS for m in re.findall(p, text)}


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (voucher-source-watcher; +github-actions)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    return normalise(text)


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

        old_sig, new_sig = signals(old_text), signals(new_text)
        if old_text and old_sig != new_sig:
            changed.append(name)
            added = ", ".join(f"`{s}`" for s in sorted(new_sig - old_sig)) or "none"
            removed = ", ".join(f"`{s}`" for s in sorted(old_sig - new_sig)) or "none"
            summary_lines.append(f"- **{name}** ({url}): voucher details changed — added: {added}; removed: {removed}")
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
