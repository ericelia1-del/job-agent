"""
main.py — Job fetcher using Anthropic web search + RSS fallback
Searches the real web (LinkedIn, Indeed, company sites) for sales leadership roles
matching Eric's background. Falls back to RSS feeds as supplementary sources.
"""

import os
import json
import re
import time
from typing import List, Dict, Any

import requests
import feedparser
import pandas as pd

OUTPUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "remote_jobs.csv")

ERIC_SEARCH_QUERIES = [
    "site:linkedin.com/jobs VP Sales remote 2025",
    "site:linkedin.com/jobs Director of Sales remote",
    "site:linkedin.com/jobs Sales Manager remote $100k",
    "site:linkedin.com/jobs Senior Account Executive remote SaaS",
    "site:indeed.com VP of Sales remote job",
    "site:indeed.com Director Sales remote full time",
    "site:indeed.com Regional Sales Manager remote",
    "site:indeed.com Sales Director remote $100000",
    "site:glassdoor.com VP Sales remote job 2025",
    "site:glassdoor.com Director of Sales remote",
    "remote VP Sales job 2025 apply",
    "remote Director of Sales job 2025 apply",
    "remote Sales Manager $120k job 2025",
    "remote enterprise account executive $100k 2025",
    "remote head of sales SaaS job 2025",
    "remote general sales manager job 2025",
    "remote regional sales manager job apply 2025",
    "remote business development director job 2025",
    "remote customer success director $100k 2025",
    "remote senior account executive B2B 2025",
]

BAD_TERMS = [
    "commission only", "commission-only", "door to door", "door-to-door",
    "1099 only", "mlm", "pyramid", "final expense", "insurance agent",
    "entry level", "internship", "unpaid", "no experience required",
]


# ── Web Search via Anthropic ──────────────────────────────────────

def fetch_via_web_search(api_key: str) -> List[Dict[str, Any]]:
    """Use Claude with web_search tool to find real job listings."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    jobs = []

    print("  Searching the web for jobs via Claude...")

    search_prompt = """Search for current remote sales leadership job openings that match this candidate:

Eric Elia - 8+ years managing sales teams (up to 17 people), $5M+ annual gross profit,
proven team leader in high-volume sales environments, Marine Corps veteran.
Open to ANY industry. Needs $100k+ total comp. Location: Palm Harbor FL, open to relocation.

His transferable skills: team leadership, pipeline management, deal structuring, 
KPI accountability, coaching/developing sales reps, consultative selling, CRM proficiency,
process improvement, revenue growth, customer relationship management.

Search for these roles (any industry): 
"remote sales manager job", "remote regional sales manager",
"remote director of sales", "remote general sales manager",
"remote senior account executive", "remote business development manager",
"remote customer success manager $100k", "remote sales director",
"remote area sales manager", "remote district sales manager",
"remote national sales manager", "remote VP sales",
"remote head of sales", "sales leadership remote job 2025"

For each job found, extract:
- Job title
- Company name  
- Job URL (direct link to apply)
- Brief description (what industry, team size if mentioned, comp if mentioned)

Return results as a JSON array with fields: title, company, url, description
Find 25-40 jobs. Prioritize roles that involve managing a sales team and have $100k+ realistic earnings.
Include jobs from automotive, real estate, healthcare, logistics, construction, B2B services,
financial services, staffing, manufacturing — not just tech."""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": search_prompt}],
        )

        # Extract text from response
        full_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                full_text += block.text

        # Try to parse JSON from the response
        json_match = re.search(r'\[[\s\S]*\]', full_text)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                for item in parsed:
                    if isinstance(item, dict) and item.get("title"):
                        jobs.append({
                            "source": "Web Search",
                            "title": item.get("title", ""),
                            "company": item.get("company", "") or "Unknown",
                            "location": "Remote",
                            "url": item.get("url", "") or item.get("link", ""),
                            "published": "",
                            "description": item.get("description", "") or item.get("summary", ""),
                        })
            except json.JSONDecodeError:
                pass

        # Also extract any job-like patterns from raw text if JSON parse failed
        if not jobs:
            lines = full_text.split("\n")
            current_job = {}
            for line in lines:
                line = line.strip()
                if not line:
                    if current_job.get("title"):
                        jobs.append({
                            "source": "Web Search",
                            "title": current_job.get("title", ""),
                            "company": current_job.get("company", "Unknown"),
                            "location": "Remote",
                            "url": current_job.get("url", ""),
                            "published": "",
                            "description": current_job.get("description", ""),
                        })
                    current_job = {}
                elif "title" in line.lower() and ":" in line:
                    current_job["title"] = line.split(":", 1)[-1].strip().strip('"')
                elif "company" in line.lower() and ":" in line:
                    current_job["company"] = line.split(":", 1)[-1].strip().strip('"')
                elif "url" in line.lower() and ":" in line:
                    url_part = line.split(":", 1)[-1].strip().strip('"')
                    if url_part.startswith("http"):
                        current_job["url"] = url_part
                elif "description" in line.lower() and ":" in line:
                    current_job["description"] = line.split(":", 1)[-1].strip().strip('"')

        print(f"    Found {len(jobs)} jobs via web search")

    except Exception as e:
        print(f"  Web search error: {e}")

    return jobs


# ── RSS Fallback Sources ──────────────────────────────────────────

def fetch_remotive() -> List[Dict[str, Any]]:
    jobs = []
    try:
        for cat in ["sales", "business-development", "management-finance"]:
            r = requests.get(
                f"https://remotive.com/api/remote-jobs?category={cat}&limit=100",
                timeout=20,
            )
            r.raise_for_status()
            for item in r.json().get("jobs", []):
                jobs.append({
                    "source": "Remotive",
                    "title": item.get("title", ""),
                    "company": item.get("company_name", "") or "Unknown",
                    "location": item.get("candidate_required_location", "Remote"),
                    "url": item.get("url", ""),
                    "published": item.get("publication_date", ""),
                    "description": item.get("description", "") or "",
                    "salary": item.get("salary", ""),
                })
    except Exception as e:
        print(f"  Remotive error: {e}")
    return jobs


def fetch_jobicy() -> List[Dict[str, Any]]:
    jobs = []
    try:
        for industry in ["sales", "management"]:
            r = requests.get(
                f"https://jobicy.com/api/v2/remote-jobs?count=100&industry={industry}",
                timeout=20,
            )
            r.raise_for_status()
            for item in r.json().get("jobs", []):
                jobs.append({
                    "source": "Jobicy",
                    "title": item.get("jobTitle", ""),
                    "company": item.get("companyName", "") or "Unknown",
                    "location": "Remote",
                    "url": item.get("url", ""),
                    "published": item.get("pubDate", ""),
                    "description": item.get("jobDescription", "") or "",
                    "salary": item.get("annualSalaryMin", ""),
                })
    except Exception as e:
        print(f"  Jobicy error: {e}")
    return jobs


def fetch_we_work_remotely() -> List[Dict[str, Any]]:
    jobs = []
    try:
        feed = feedparser.parse("https://weworkremotely.com/remote-jobs.rss")
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
    except Exception as e:
        print(f"  WWR error: {e}")
    return jobs


def fetch_remoteok() -> List[Dict[str, Any]]:
    jobs = []
    try:
        r = requests.get(
            "https://remoteok.com/api",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        r.raise_for_status()
        for item in r.json():
            if not isinstance(item, dict) or not item.get("position"):
                continue
            jobs.append({
                "source": "Remote OK",
                "title": item.get("position", ""),
                "company": item.get("company", "") or "Unknown",
                "location": item.get("location", "") or "Remote",
                "url": item.get("url", ""),
                "published": item.get("date", ""),
                "description": item.get("description", "") or "",
            })
    except Exception as e:
        print(f"  RemoteOK error: {e}")
    return jobs


def fetch_himalayas() -> List[Dict[str, Any]]:
    jobs = []
    try:
        for role in ["sales-manager", "account-executive", "director-of-sales",
                     "vp-sales", "business-development-manager", "customer-success-manager"]:
            r = requests.get(
                f"https://himalayas.app/jobs/api?role={role}&limit=50",
                timeout=20,
            )
            if r.status_code != 200:
                continue
            for item in r.json().get("jobs", []):
                jobs.append({
                    "source": "Himalayas",
                    "title": item.get("title", ""),
                    "company": item.get("company", {}).get("name", "") or "Unknown",
                    "location": "Remote",
                    "url": item.get("applicationUrl", item.get("url", "")),
                    "published": item.get("createdAt", ""),
                    "description": item.get("description", "") or "",
                    "salary": item.get("salary", ""),
                })
    except Exception as e:
        print(f"  Himalayas error: {e}")
    return jobs


# ── Scoring & Dedup ───────────────────────────────────────────────

GOOD_TERMS = [
    "sales", "revenue", "leadership", "director", "manager", "vp",
    "account executive", "business development", "customer success",
    "quota", "pipeline", "territory", "saas", "remote", "b2b",
    "team", "coaching", "fintech", "enterprise", "strategic",
]

SEARCH_TERMS = [
    "vp of sales", "vp sales", "director of sales", "sales director",
    "head of sales", "sales manager", "regional sales manager",
    "senior account executive", "business development director",
    "customer success manager", "account executive", "revenue director",
    "enterprise sales", "general sales manager", "national sales manager",
]

def score_job(job: Dict[str, Any]) -> int:
    text = " ".join([
        job.get("title", ""), job.get("company", ""),
        job.get("description", ""),
    ]).lower()
    score = sum(2 for t in GOOD_TERMS if t in text)
    score += sum(3 for t in SEARCH_TERMS if t in text)
    score -= sum(5 for t in BAD_TERMS if t in text)
    return max(score, 0)


def dedupe(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for job in jobs:
        key = (
            job.get("title", "").strip().lower()[:60],
            job.get("company", "").strip().lower()[:40],
        )
        if key not in seen:
            seen.add(key)
            out.append(job)
    return out


# ── Main ─────────────────────────────────────────────────────────

def main():
    print("Fetching jobs from all sources...")
    jobs = []

    # Primary: web search (requires API key in env)
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if api_key:
        web_jobs = fetch_via_web_search(api_key)
        jobs.extend(web_jobs)
        print(f"  Web search total: {len(web_jobs)} jobs")
    else:
        print("  No ANTHROPIC_API_KEY — skipping web search")

    # Supplementary RSS/API sources
    prev = len(jobs)
    jobs.extend(fetch_remotive())
    print(f"  Remotive: {len(jobs) - prev} jobs")

    prev = len(jobs)
    jobs.extend(fetch_jobicy())
    print(f"  Jobicy: {len(jobs) - prev} jobs")

    prev = len(jobs)
    jobs.extend(fetch_himalayas())
    print(f"  Himalayas: {len(jobs) - prev} jobs")

    prev = len(jobs)
    jobs.extend(fetch_we_work_remotely())
    print(f"  We Work Remotely: {len(jobs) - prev} jobs")

    prev = len(jobs)
    jobs.extend(fetch_remoteok())
    print(f"  Remote OK: {len(jobs) - prev} jobs")

    jobs = dedupe(jobs)
    print(f"\nTotal unique jobs: {len(jobs)}")

    # Score and filter — only remove hard negatives
    ranked = []
    for job in jobs:
        job["score"] = score_job(job)
        text = f"{job.get('title','').lower()} {job.get('description','').lower()}"
        if not any(t in text for t in BAD_TERMS):
            ranked.append(job)

    ranked = sorted(ranked, key=lambda x: x["score"], reverse=True)

    df = pd.DataFrame(ranked)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved {len(ranked)} jobs to {OUTPUT_CSV}")

    print("\nTop 10:")
    for i, job in enumerate(ranked[:10], 1):
        print(f"{i}. [{job.get('source')}] {job.get('title')} @ {job.get('company')} | score={job.get('score',0)}")
        print(f"   {job.get('url','')}")


if __name__ == "__main__":
    main()
