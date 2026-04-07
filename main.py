import os
import json
from datetime import datetime
from typing import List, Dict, Any

import requests
import feedparser
import pandas as pd

OUTPUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "remote_jobs.csv")

SEARCH_TERMS = [
    "account executive",
    "business development manager",
    "business development representative",
    "inside sales manager",
    "regional sales manager",
    "sales director",
    "customer success manager",
    "partner manager",
    "territory manager",
    "revenue operations",
    "remote sales",
]

GOOD_TERMS = [
    "remote",
    "sales",
    "revenue",
    "leadership",
    "customer success",
    "account executive",
    "business development",
    "partnerships",
    "manager",
    "director",
    "team leadership",
    "coaching",
    "hiring",
    "growth",
]

BAD_TERMS = [
    "insurance",
    "commission only",
    "door to door",
    "1099 only",
    "mlm",
    "final expense",
    "licensed insurance",
]
def fetch_we_work_remotely() -> List[Dict[str, Any]]:
    feed = feedparser.parse("https://weworkremotely.com/remote-jobs.rss")
    jobs = []
    for entry in feed.entries:
        jobs.append({
            "source": "We Work Remotely",
            "title": entry.get("title", ""),
            "company": entry.get("author", "") or "Unknown",
            "location": "Remote",
            "url": entry.get("link", ""),
            "published": entry.get("published", ""),
            "description": entry.get("summary", ""),
        })
    return jobs

def fetch_remoteok() -> List[Dict[str, Any]]:
    jobs = []
    try:
        r = requests.get("https://remoteok.com/api", headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                title = item.get("position", "")
                if not title:
                    continue
                jobs.append({
                    "source": "Remote OK",
                    "title": title,
                    "company": item.get("company", "") or "Unknown",
                    "location": item.get("location", "") or "Remote",
                    "url": item.get("url", ""),
                    "published": item.get("date", ""),
                    "description": item.get("description", "") or "",
                })
    except Exception as e:
        print(f"Could not load Remote OK: {e}")
    return jobs

def score_job(job: Dict[str, Any]) -> int:
    text = " ".join([
        job.get("title", ""),
        job.get("company", ""),
        job.get("location", ""),
        job.get("description", ""),
    ]).lower()

    score = 0
    for term in GOOD_TERMS:
        if term in text:
            score += 2
    for term in SEARCH_TERMS:
        if term in text:
            score += 3
    for term in BAD_TERMS:
        if term in text:
            score -= 4
    if "remote" in text:
        score += 2
    return max(score, 0)

def is_relevant(job: Dict[str, Any]) -> bool:
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()
    return any(term in text for term in SEARCH_TERMS)

def dedupe(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    cleaned = []
    for job in jobs:
        key = (
            job.get("title", "").strip().lower(),
            job.get("company", "").strip().lower(),
            job.get("url", "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(job)
    return cleaned

def main():
    jobs = []
    jobs.extend(fetch_we_work_remotely())
    jobs.extend(fetch_remoteok())
    jobs = dedupe(jobs)

    ranked = []
    for job in jobs:
        job["score"] = score_job(job)
        if is_relevant(job) or job["score"] >= 5:
            ranked.append(job)

    ranked = sorted(ranked, key=lambda x: x["score"], reverse=True)

    df = pd.DataFrame(ranked)
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"Saved {len(ranked)} jobs to {OUTPUT_CSV}")
    print("Top 10:")
    for i, job in enumerate(ranked[:10], start=1):
        print(f"{i}. {job.get('title', 'Unknown')} | {job.get('company', 'Unknown')} | score={job.get('score', 0)}")
        print(f"   {job.get('url', '')}")

if __name__ == "__main__":
    main()
