#!/usr/bin/env python3
"""
Fetch posts from Reddit r/wallstreetbets across multiple listings and export
normalized JSON and CSV files.

This script uses Reddit's public JSON endpoints (no auth required) with a
polite User-Agent and supports pagination via the `after` cursor. Listings
supported: hot, new, top, rising, and a search sorted by comments ("comments").

Output files:
 - outputs/wallstreetbets_raw_<listing>.json
 - outputs/wallstreetbets_normalized.json
 - outputs/wallstreetbets_normalized.csv
 - outputs/wallstreetbets_metadata.json

Note: "All posts" is unbounded; use --max-pages to control pagination.
"""

import argparse
import csv
import json
import os
import sys
import time
from typing import Dict, List, Tuple

try:
    import requests
except ImportError:
    print("The 'requests' package is required. Install with: pip install requests", file=sys.stderr)
    sys.exit(1)


USER_AGENT = "CodexCLI-AI/1.0 (fetch_wsb_reddit.py)"


def reddit_get(url: str, params: Dict[str, str]) -> Dict:
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_listing(subreddit: str, listing: str, max_pages: int, top_time: str = "all", sleep_s: float = 1.0) -> List[Dict]:
    """Fetch a listing (hot/new/top/rising) with pagination."""
    base = f"https://www.reddit.com/r/{subreddit}/{listing}.json"
    params: Dict[str, str] = {"limit": "100"}
    if listing == "top":
        params["t"] = top_time  # all, year, month, week, day, hour

    after = None
    page = 0
    items: List[Dict] = []
    while True:
        page += 1
        if after:
            params["after"] = after
        else:
            params.pop("after", None)

        data = reddit_get(base, params)
        children = data.get("data", {}).get("children", [])
        if not children:
            break
        for c in children:
            if c.get("kind") == "t3" and isinstance(c.get("data"), dict):
                items.append(c["data"])  # submission data

        after = data.get("data", {}).get("after")
        if not after:
            break
        if page >= max_pages:
            break
        time.sleep(sleep_s)
    return items


def fetch_search_comments(subreddit: str, max_pages: int, sleep_s: float = 1.0) -> List[Dict]:
    """Fetch posts via search sorted by number of comments (may include duplicates)."""
    base = "https://www.reddit.com/search.json"
    params: Dict[str, str] = {
        "q": f"subreddit:{subreddit}",
        "restrict_sr": "on",
        "sort": "comments",
        "limit": "100",
    }

    after = None
    page = 0
    items: List[Dict] = []
    while True:
        page += 1
        if after:
            params["after"] = after
        else:
            params.pop("after", None)

        data = reddit_get(base, params)
        children = data.get("data", {}).get("children", [])
        if not children:
            break
        for c in children:
            if c.get("kind") == "t3" and isinstance(c.get("data"), dict):
                items.append(c["data"])  # submission data

        after = data.get("data", {}).get("after")
        if not after:
            break
        if page >= max_pages:
            break
        time.sleep(sleep_s)
    return items


def normalize_post(d: Dict, source_listing: str) -> Dict:
    """Extract the required fields and add provenance info."""
    # Base fields from Reddit submission JSON
    base_id = d.get("id")  # base36 id
    title = d.get("title", "")
    author = d.get("author", "")
    score = d.get("score", 0)
    num_comments = d.get("num_comments", 0)
    created_utc = d.get("created_utc", None)
    permalink = d.get("permalink", "")
    url = d.get("url", "")
    flair = d.get("link_flair_text", None)
    selftext = d.get("selftext", "")

    return {
        "id": base_id,
        "title": title,
        "author": author,
        "score": score,
        "num_comments": num_comments,
        "created_utc": created_utc,
        "permalink": permalink,
        "url": url,
        "flair": flair,
        "selftext": selftext,
        "source_listing": source_listing,
    }


def dedupe_merge(records: List[Dict]) -> List[Dict]:
    """Deduplicate by id; keep the record with highest score, then more complete fields."""
    by_id: Dict[str, Dict] = {}
    for r in records:
        rid = r.get("id")
        if not rid:
            # Skip items without ID (shouldn't happen for t3)
            continue
        prev = by_id.get(rid)
        if not prev:
            by_id[rid] = r
        else:
            # Choose record with higher score; if equal, prefer longer selftext; if equal, prefer one with flair
            def completeness(rec: Dict) -> Tuple[int, int, int]:
                score = int(rec.get("score") or 0)
                self_len = len(rec.get("selftext") or "")
                flair_present = 1 if rec.get("flair") else 0
                return (score, self_len, flair_present)

            if completeness(r) > completeness(prev):
                by_id[rid] = r
            else:
                # Merge provenance: append source_listing if different
                sources = set()
                for s in (prev.get("source_listing"), r.get("source_listing")):
                    if s:
                        sources.update(s if isinstance(s, list) else [s])
                prev["source_listing"] = sorted(list(sources))
                by_id[rid] = prev

    return list(by_id.values())


def write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_csv(path: str, records: List[Dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cols = [
        "id",
        "title",
        "author",
        "score",
        "num_comments",
        "created_utc",
        "permalink",
        "url",
        "flair",
        "selftext",
        "source_listing",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in records:
            row = {k: r.get(k) for k in cols}
            # Ensure strings are not None
            for k, v in row.items():
                if v is None:
                    row[k] = ""
            w.writerow(row)


def compute_summary(records: List[Dict]) -> Dict:
    ids = [r.get("id") for r in records if r.get("id")]
    unique_ids = len(set(ids))
    total = len(records)
    duplicates_removed = total - unique_ids
    created_vals = [r.get("created_utc") for r in records if r.get("created_utc")]
    earliest = min(created_vals) if created_vals else None
    latest = max(created_vals) if created_vals else None
    # Top authors by count
    author_counts: Dict[str, int] = {}
    for r in records:
        a = r.get("author") or ""
        if a:
            author_counts[a] = author_counts.get(a, 0) + 1
    top_authors = sorted(author_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
    return {
        "total_records_exported": total,
        "unique_ids": unique_ids,
        "duplicates_removed": duplicates_removed,
        "earliest_created_utc": earliest,
        "latest_created_utc": latest,
        "top_10_authors_by_count": top_authors,
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch r/wallstreetbets posts and export normalized JSON/CSV")
    parser.add_argument("--subreddit", default="wallstreetbets", help="Target subreddit name without 'r/'")
    parser.add_argument(
        "--listings",
        default="hot,new,top,rising,comments",
        help="Comma-separated listing types to fetch (hot,new,top,rising,comments)",
    )
    parser.add_argument("--max-pages", type=int, default=10, help="Max pages per listing (100 items per page)")
    parser.add_argument("--top-time", default="all", help="Time filter for top listing: all, year, month, week, day, hour")
    parser.add_argument("--sleep", type=float, default=0.8, help="Sleep seconds between pages to avoid rate limiting")
    parser.add_argument("--output-dir", default="outputs", help="Directory to store outputs")
    args = parser.parse_args()

    listings = [s.strip() for s in args.listings.split(",") if s.strip()]

    all_records: List[Dict] = []
    raw_by_listing: Dict[str, List[Dict]] = {}

    for listing in listings:
        print(f"Fetching listing: {listing}")
        if listing in {"hot", "new", "top", "rising"}:
            raw = fetch_listing(args.subreddit, listing, args.max_pages, args.top_time, args.sleep)
        elif listing == "comments":
            raw = fetch_search_comments(args.subreddit, args.max_pages, args.sleep)
        else:
            print(f"Unknown listing '{listing}', skipping", file=sys.stderr)
            continue

        raw_by_listing[listing] = raw
        # Write raw file
        raw_path = os.path.join(args.output_dir, f"wallstreetbets_raw_{listing}.json")
        write_json(raw_path, raw)
        print(f"Saved {len(raw)} raw items to {raw_path}")

        # Normalize
        normalized = [normalize_post(d, listing) for d in raw]
        all_records.extend(normalized)

    # Deduplicate + merge
    merged = dedupe_merge(all_records)

    # Exports
    normalized_json_path = os.path.join(args.output_dir, "wallstreetbets_normalized.json")
    normalized_csv_path = os.path.join(args.output_dir, "wallstreetbets_normalized.csv")
    write_json(normalized_json_path, merged)
    write_csv(normalized_csv_path, merged)

    # Summary
    meta = compute_summary(merged)
    metadata_path = os.path.join(args.output_dir, "wallstreetbets_metadata.json")
    write_json(metadata_path, meta)
    print(f"Summary saved to {metadata_path}")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()

