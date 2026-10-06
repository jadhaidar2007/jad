"""Read a pasted Whop (or other) clipping-campaign listing and say GO / CAUTION / NO-GO.

    python analyze_campaign.py listing.txt --country germany --platforms tiktok
    pbpaste | python analyze_campaign.py - --country germany     # macOS clipboard

It extracts the requirements with the LLM, checks them against YOUR situation in code
(country, platforms), prints a report, and writes a clean rulebook you can pass on:

    python run_one.py "<source url>" --rulebook-file rulebook.txt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from clipengine import config, llm

SYSTEM = """You read a content-clipping campaign listing and extract its requirements.
Return STRICT JSON with exactly these keys (null / [] / "" when the listing does not say;
never guess or invent):
{"campaign_name": str, "pay_rate_per_1k_views": number|null, "currency": str,
 "cap_per_clip": number|null, "total_budget": number|null, "min_views_to_get_paid": number|null,
 "valid_view_rules": str, "payout_timing": str,
 "audience_requirements": [{"countries": [str], "min_percent": number|null}],
 "allowed_platforms": [str], "content_source": str, "source_links": [str],
 "clip_length_min_s": number|null, "clip_length_max_s": number|null,
 "required_hashtags": [str], "required_mentions": [str], "required_text_or_watermark": str,
 "banned_content": [str], "other_clip_rules": [str], "submission_process": str,
 "red_flags": [str]}
red_flags: anything suspicious or unclear for a clipper (unrealistic pay, pay-to-join, asks for
account logins, vague payout terms, no way to verify views, rights unclear)."""

ALIASES = {
    "de": "germany", "deutschland": "germany",
    "us": "united states", "usa": "united states", "america": "united states",
    "uk": "united kingdom", "gb": "united kingdom", "britain": "united kingdom", "england": "united kingdom",
    "ca": "canada", "au": "australia",
}


def canon(name: str) -> str:
    n = name.strip().lower()
    return ALIASES.get(n, n)


def verdict(d: dict, country: str, platforms: list[str]) -> tuple[str, list[str]]:
    level, notes = "GO", []

    def worse(new: str) -> None:
        nonlocal level
        order = {"GO": 0, "CAUTION": 1, "NO-GO": 2}
        if order[new] > order[level]:
            level = new

    allowed = [canon(p) for p in d.get("allowed_platforms") or []]
    if allowed and not any(canon(p) in allowed for p in platforms):
        worse("NO-GO"); notes.append(f"Campaign only allows {d['allowed_platforms']}; you post to {platforms}.")

    for req in d.get("audience_requirements") or []:
        countries = [canon(c) for c in req.get("countries") or []]
        pct = req.get("min_percent")
        if countries and canon(country) not in countries:
            worse("CAUTION")
            notes.append(
                f"Audience rule: {pct or '?'}% from {req.get('countries')}; you are in {country}. "
                "Only reachable with English-language, US/UK-focused content and a lot of luck; "
                "ask the owner how it is verified before investing time."
            )

    rate = d.get("pay_rate_per_1k_views")
    if rate is None:
        worse("CAUTION"); notes.append("No pay rate found in the listing.")
    elif rate < 0.5:
        worse("CAUTION"); notes.append(f"Low rate ({rate}/1k views); real payouts are usually below the listed rate.")
    if d.get("cap_per_clip") is not None and rate:
        full = d["cap_per_clip"] / rate * 1000
        notes.append(f"Per-clip cap hit at about {full:,.0f} views.")
    if d.get("red_flags"):
        worse("CAUTION"); notes += [f"Red flag: {f}" for f in d["red_flags"]]
    if not d.get("source_links") and not d.get("content_source"):
        worse("CAUTION"); notes.append("No clear content source; confirm you are allowed to clip it.")
    return level, notes


def build_rulebook(d: dict) -> str:
    parts = []
    if d.get("clip_length_min_s") or d.get("clip_length_max_s"):
        parts.append(f"Clip length {d.get('clip_length_min_s') or 'any'}-{d.get('clip_length_max_s') or 'any'} seconds.")
    if d.get("required_hashtags"):
        parts.append("Required hashtags: " + " ".join(d["required_hashtags"]) + ".")
    if d.get("required_mentions"):
        parts.append("Must tag: " + " ".join(d["required_mentions"]) + ".")
    if d.get("banned_content"):
        parts.append("Do not include: " + "; ".join(d["banned_content"]) + ".")
    parts += d.get("other_clip_rules") or []
    return " ".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("listing", help="file with the pasted listing, or - for stdin")
    ap.add_argument("--country", default="germany", help="the country your account/audience is in")
    ap.add_argument("--platforms", default="tiktok", help="comma list of platforms you will post to")
    ap.add_argument("--rulebook-out", default="rulebook.txt")
    args = ap.parse_args()

    text = sys.stdin.read() if args.listing == "-" else Path(args.listing).read_text()
    if not text.strip():
        print("Listing is empty."); return 1
    if not config.DEEPSEEK_API_KEY:
        print("DEEPSEEK_API_KEY not set in .env"); return 1

    d = llm.chat_json(SYSTEM, text.strip()[:30000], max_tokens=2500)
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    level, notes = verdict(d, args.country, platforms)

    print(f"\n{level}: {d.get('campaign_name') or 'campaign'}")
    print(f"  Pay: {d.get('pay_rate_per_1k_views')} {d.get('currency') or ''} per 1k views | cap/clip: {d.get('cap_per_clip')} | budget: {d.get('total_budget')}")
    print(f"  Paid after: {d.get('min_views_to_get_paid')} views | payout: {d.get('payout_timing') or 'not stated'}")
    print(f"  Valid views: {d.get('valid_view_rules') or 'not stated'}")
    print(f"  Source: {d.get('content_source') or 'not stated'} {d.get('source_links') or ''}")
    print(f"  Submit: {d.get('submission_process') or 'not stated'}")
    print("\nNotes:")
    for n in notes or ["No issues found."]:
        print(f"  - {n}")

    rulebook = build_rulebook(d)
    Path(args.rulebook_out).write_text(rulebook)
    print(f"\nRulebook for the clip engine written to {args.rulebook_out}:\n  {rulebook or '(none found)'}")
    print("\nThis is an automated reading. Check the original listing before you join or post.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
