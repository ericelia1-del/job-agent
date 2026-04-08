import os
import json
from datetime import datetime
from typing import List, Dict, Any

import requests
import feedparser
import pandas as pd

OUTPUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "remote_jobs.csv")

SEARCH_TERMS = [
    # Leadership titles
    "sales manager", "regional sales manager", "area sales manager",
    "district sales manager", "national sales manager", "general sales manager",
    "director of sales", "sales director", "head of sales",
    "vp of sales", "vp sales", "vice president sales",
    "revenue director", "business development director",
    # AE / BD roles
    "senior account executive", "enterprise account executive",
    "strategic account executive", "account executive",
    "business development manager", "senior business development",
    # Customer success / partnerships
    "customer success manager", "director of customer success",
    "partnerships manager", "channel sales manager",
    # General
    "sales leader", "revenue manager", "growth manager",
    "remote sales", "team lead sales",
]

GOOD_TERMS = [
    "remote", "sales", "revenue", "leadership", "customer success",
    "account executive", "business development", "partnerships",
    "manager", "director", "team leadership", "coaching",
    "hiring", "growth", "saas", "fintech", "quota", "pipeline",
    "forecasting", "kpi", "consultative", "territory",
]

BAD_TERMS = [
    "insurance", "commission only", "door to door",
    "1099 only", "mlm", "final expense", "licensed insurance",
    "entry level", "internship", "unpaid",
]


# ── Sources ──────────────────────────────────────────────────────

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
        print(f"We Work Remotely error: {e}")
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
        data = r.json()
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
        print(f"Remote OK error: {e}")
    return jobs


def fetch_remotive() -> List[Dict[str, Any]]:
    jobs = []
    try:
        categories = ["sales", "business-development", "management-finance"]
        for cat in categories:
            r = requests.get(
                f"https://remotive.com/api/remote-jobs?category={cat}&limit=50",
                timeout=20,
            )
            r.raise_for_status()
            data = r.json().get("jobs", [])
            for item in data:
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
        print(f"Remotive error: {e}")
    return jobs


def fetch_jobicy() -> List[Dict[str, Any]]:
    jobs = []
    try:
        r = requests.get(
            "https://jobicy.com/api/v2/remote-jobs?count=50&industry=sales",
            timeout=20,
        )
        r.raise_for_status()
        data = r.json().get("jobs", [])
        for item in data:
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
        print(f"Jobicy error: {e}")
    return jobs


def fetch_arbeitnow() -> List[Dict[str, Any]]:
    jobs = []
    try:
        r = requests.get(
            "https://www.arbeitnow.com/api/job-board-api",
            timeout=20,
        )
        r.raise_for_status()
        data = r.json().get("data", [])
        for item in data:
            if not item.get("remote", False):
                continue
            jobs.append({
                "source": "Arbeitnow",
                "title": item.get("title", ""),
                "company": item.get("company_name", "") or "Unknown",
                "location": "Remote",
                "url": item.get("url", ""),
                "published": item.get("created_at", ""),
                "description": item.get("description", "") or "",
            })
    except Exception as e:
        print(f"Arbeitnow error: {e}")
    return jobs


def fetch_himalayas() -> List[Dict[str, Any]]:
    jobs = []
    try:
        for role in ["sales-manager", "account-executive", "director-of-sales", "vp-sales"]:
            r = requests.get(
                f"https://himalayas.app/jobs/api?role={role}&limit=25",
                timeout=20,
            )
            if r.status_code != 200:
                continue
            data = r.json().get("jobs", [])
            for item in data:
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
        print(f"Himalayas error: {e}")
    return jobs


def fetch_indeed_rss() -> List[Dict[str, Any]]:
    """Search Indeed via RSS for targeted role titles."""
    jobs = []
    queries = [
        # Leadership
        "Sales+Manager+remote+100000",
        "Regional+Sales+Manager+remote",
        "Director+of+Sales+remote",
        "Head+of+Sales+remote",
        "VP+Sales+remote",
        "General+Sales+Manager+remote",
        "National+Sales+Manager+remote",
        # AE / BD
        "Senior+Account+Executive+remote",
        "Enterprise+Account+Executive+remote",
        "Business+Development+Manager+remote",
        "Business+Development+Director+remote",
        # Customer success
        "Customer+Success+Manager+remote+100000",
        "Director+Customer+Success+remote",
        # Industry specific
        "Sales+Director+SaaS+remote",
        "Sales+Manager+SaaS+remote",
        "Sales+Manager+fintech+remote",
        "Regional+Sales+Manager+healthcare",
        "Sales+Manager+logistics+remote",
        "Sales+Director+real+estate+remote",
        "Account+Executive+enterprise+remote",
    ]
    for q in queries:
        try:
            url = f"https://www.indeed.com/rss?q={q}&sort=date&fromage=14"
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.get("title", "")
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    job_title = parts[0].strip()
                    company = parts[1].strip() if len(parts) > 1 else "Unknown"
                else:
                    job_title = title
                    company = "Unknown"
                jobs.append({
                    "source": "Indeed",
                    "title": job_title,
                    "company": company,
                    "location": "Remote",
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "description": entry.get("summary", ""),
                })
        except Exception as e:
            print(f"Indeed RSS error ({q}): {e}")
    return jobs


def fetch_linkedin_rss() -> List[Dict[str, Any]]:
    """Fetch LinkedIn job RSS feeds for targeted searches."""
    jobs = []
    searches = [
        ("VP Sales", "102571732"),       # United States geoId
        ("Director of Sales", "102571732"),
        ("Head of Sales remote", "102571732"),
        ("Sales Director SaaS", "102571732"),
        ("Enterprise Account Executive", "102571732"),
    ]
    for keywords, geo in searches:
        try:
            kw = keywords.replace(" ", "%20")
            url = f"https://www.linkedin.com/jobs/search/?keywords={kw}&location=Remote&f_WT=2&f_TPR=r604800&position=1&pageNum=0"
            # LinkedIn RSS feed
            rss_url = f"https://www.linkedin.com/jobs/search/?keywords={kw}&f_WT=2&f_TPR=r604800"
            r = requests.get(
                rss_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; RSS reader)"},
                timeout=15,
            )
            feed = feedparser.parse(r.content)
            for entry in feed.entries:
                jobs.append({
                    "source": "LinkedIn",
                    "title": entry.get("title", ""),
                    "company": entry.get("author", "") or "Unknown",
                    "location": "Remote",
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "description": entry.get("summary", ""),
                })
        except Exception as e:
            print(f"LinkedIn RSS error ({keywords}): {e}")
    return jobs


def fetch_otta() -> List[Dict[str, Any]]:
    """Fetch from Otta (tech-focused job board)."""
    jobs = []
    try:
        r = requests.get(
            "https://api.otta.com/graphql",
            json={"query": '{ jobs(filters: {remote: true, functionIds: ["sales"]}) { edges { node { title company { name } externalUrl } } } }'},
            timeout=15,
        )
        if r.status_code == 200:
            edges = r.json().get("data", {}).get("jobs", {}).get("edges", [])
            for edge in edges:
                node = edge.get("node", {})
                jobs.append({
                    "source": "Otta",
                    "title": node.get("title", ""),
                    "company": node.get("company", {}).get("name", "") or "Unknown",
                    "location": "Remote",
                    "url": node.get("externalUrl", ""),
                    "published": "",
                    "description": "",
                })
    except Exception as e:
        print(f"Otta error: {e}")
    return jobs


# ── Scoring & Filtering ───────────────────────────────────────────

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
    print("Fetching jobs from all sources...")
    jobs = []

    prev = 0
    jobs.extend(fetch_we_work_remotely())
    print(f"  We Work Remotely: {len(jobs) - prev} jobs")

    prev = len(jobs)
    jobs.extend(fetch_remoteok())
    print(f"  Remote OK: {len(jobs) - prev} jobs")

    prev = len(jobs)
    jobs.extend(fetch_remotive())
    print(f"  Remotive: {len(jobs) - prev} jobs")

    prev = len(jobs)
    jobs.extend(fetch_jobicy())
    print(f"  Jobicy: {len(jobs) - prev} jobs")

    prev = len(jobs)
    jobs.extend(fetch_arbeitnow())
    print(f"  Arbeitnow: {len(jobs) - prev} jobs")

    prev = len(jobs)
    jobs.extend(fetch_himalayas())
    print(f"  Himalayas: {len(jobs) - prev} jobs")

    prev = len(jobs)
    jobs.extend(fetch_indeed_rss())
    print(f"  Indeed RSS: {len(jobs) - prev} jobs")

    prev = len(jobs)
    jobs.extend(fetch_linkedin_rss())
    print(f"  LinkedIn RSS: {len(jobs) - prev} jobs")

    jobs = dedupe(jobs)
    print(f"\nTotal unique jobs: {len(jobs)}")

    # Score everything — exclude only hard negatives, let Claude do real filtering
    ranked = []
    for job in jobs:
        job["score"] = score_job(job)
        text = f"{job.get('title','').lower()} {job.get('description','').lower()}"
        is_bad = any(t in text for t in BAD_TERMS)
        if not is_bad:
            ranked.append(job)

    ranked = sorted(ranked, key=lambda x: x["score"], reverse=True)

    df = pd.DataFrame(ranked)
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"Saved {len(ranked)} jobs to {OUTPUT_CSV}")
    print("\nTop 10:")
    for i, job in enumerate(ranked[:10], start=1):
        print(f"{i}. [{job.get('source')}] {job.get('title')} | {job.get('company')} | score={job.get('score', 0)}")
        print(f"   {job.get('url', '')}")


if __name__ == "__main__":
    main()
