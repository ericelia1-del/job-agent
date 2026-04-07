import streamlit as st
import pandas as pd
import subprocess
import os
from datetime import datetime

# Always work relative to the folder this script lives in
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRACKER_FILE = os.path.join(BASE_DIR, "saved_jobs.csv")

# ─────────────────────────────────────────────
# ERIC'S PROFILE  — built from his actual resume
# ─────────────────────────────────────────────
MY_PROFILE = {
    "name": "Eric D. Elia",
    "location": "Palm Harbor, FL (willing to relocate)",
    "background_summary": (
        "U.S. Marine Corps veteran and sales leader with 8+ years driving multimillion-dollar "
        "revenue growth. Responsible for $5M+ in annual gross profit across leadership roles. "
        "Managed teams of up to 17 sales professionals. Ranked #1 Sales Manager in Profit Per "
        "Vehicle Retail (PVR) across the Andy Mohr Group. Helped earn the 2024 Presidents Award "
        "at Courtesy Palm Harbor Honda. Qualified Infiniti of Tampa for the Circle of Excellence "
        "recognition. Currently New Car Director at a Top 3 Infiniti dealership in the US. "
        "Seeking VP/Director/Head of Sales roles in SaaS, fintech, AI, or tech."
    ),
    "key_achievements": [
        "$5M+ cumulative annual gross profit responsibility",
        "Led teams of up to 17 sales professionals",
        "Ranked #1 Sales Manager in PVR across entire Andy Mohr Group",
        "Helped earn the 2024 Presidents Award at Courtesy Palm Harbor Honda",
        "Qualified Infiniti of Tampa for Circle of Excellence recognition",
        "Top 3 Infiniti dealership in the US by new car volume",
        "98% customer satisfaction score as Sales & Leasing Consultant",
        "Traveled to 33 countries — cross-cultural communication skills",
        "U.S. Marine Corps veteran — Technical Controller / Data Network Specialist",
        "$3M+ annual gross profit at Andy Mohr Honda",
        "$2M+ annual gross profit at Courtesy Palm Harbor Honda",
    ],
    "strong_titles": [
        "vp of sales", "vp sales", "vice president of sales",
        "director of sales", "sales director", "head of sales",
        "regional sales manager", "senior account executive",
        "business development director", "revenue director",
        "sales manager", "account executive",
        "business development manager", "customer success manager",
        "partnerships manager", "revenue operations manager",
        "growth manager", "new car director",
    ],
    "seniority_terms": [
        "director", "vp", "vice president", "head of", "senior", "manager", "lead",
    ],
    "target_industries": [
        "saas", "fintech", "ai", "tech", "software", "cloud", "startup",
    ],
    "salary_signals": [
        "$", "ote", "equity", "base salary", "compensation", "k/year", "usd", "salary range",
    ],
    "strong_keywords": [
        "sales", "revenue", "leadership", "account management",
        "business development", "customer success", "partnerships",
        "saas", "fintech", "ai", "startup", "remote", "quota",
        "pipeline", "territory", "forecasting", "kpi", "gross profit",
        "consultative", "veteran", "coaching", "team building",
    ],
    "negative_keywords": [
        "insurance", "commission-only", "door-to-door",
        "1099", "unpaid", "intern", "entry level",
    ],
}

# ─────────────────────────────────────────────
# SCORING
# ─────────────────────────────────────────────
def find_text_column(df, preferred_names):
    lower_map = {c.lower(): c for c in df.columns}
    for name in preferred_names:
        if name in lower_map:
            return lower_map[name]
    return None


def score_jobs(df):
    title_col   = find_text_column(df, ["title", "job_title", "position"])
    company_col = find_text_column(df, ["company", "company_name"])
    desc_col    = find_text_column(df, ["description", "summary", "details"])
    salary_col  = find_text_column(df, ["salary", "compensation", "pay", "salary_range"])

    if title_col is None:
        st.error("Couldn't find a title column in remote_jobs.csv.")
        return df

    searchable = df[title_col].fillna("").astype(str)
    if company_col:
        searchable = searchable + " " + df[company_col].fillna("").astype(str)
    if desc_col:
        searchable = searchable + " " + df[desc_col].fillna("").astype(str)

    score = pd.Series(0, index=df.index)

    # Title match (+3 each)
    for title in MY_PROFILE["strong_titles"]:
        score += searchable.str.contains(title, case=False, na=False).astype(int) * 3

    # Seniority signals (+2 each)
    for term in MY_PROFILE["seniority_terms"]:
        score += searchable.str.contains(term, case=False, na=False).astype(int) * 2

    # Industry fit (+2 each)
    for industry in MY_PROFILE["target_industries"]:
        score += searchable.str.contains(industry, case=False, na=False).astype(int) * 2

    # General keyword match (+1 each)
    for kw in MY_PROFILE["strong_keywords"]:
        score += searchable.str.contains(kw, case=False, na=False).astype(int)

    # Salary signals (+1 each)
    for sig in MY_PROFILE["salary_signals"]:
        score += searchable.str.contains(sig, case=False, na=False).astype(int)

    # Salary column present (+2)
    if salary_col:
        score += df[salary_col].notna().astype(int) * 2

    # Negatives (-5 each)
    for bad in MY_PROFILE["negative_keywords"]:
        score -= searchable.str.contains(bad, case=False, na=False).astype(int) * 5

    result = df.copy()
    result["fit_score"] = score
    return result.sort_values("fit_score", ascending=False)


def filter_by_query(df, query):
    title_col   = find_text_column(df, ["title", "job_title", "position"])
    company_col = find_text_column(df, ["company", "company_name"])
    desc_col    = find_text_column(df, ["description", "summary", "details"])

    searchable = df[title_col].fillna("").astype(str)
    if company_col:
        searchable = searchable + " " + df[company_col].fillna("").astype(str)
    if desc_col:
        searchable = searchable + " " + df[desc_col].fillna("").astype(str)

    words = [w.strip() for w in query.lower().split() if w.strip()]
    mask = pd.Series(False, index=df.index)
    for w in words:
        mask |= searchable.str.contains(w, case=False, na=False)

    return df[mask]


def apply_salary_filter(df, min_salary_k):
    """Filter out jobs that explicitly mention a salary below the minimum."""
    if min_salary_k <= 80:
        return df  # No filter at the minimum
    desc_col   = find_text_column(df, ["description", "summary", "details"])
    salary_col = find_text_column(df, ["salary", "compensation", "pay", "salary_range"])
    # If salary column exists, try to filter numerically
    if salary_col:
        def salary_ok(val):
            if pd.isna(val):
                return True
            s = str(val).replace(",", "").replace("$", "")
            import re
            nums = re.findall(r"\d+", s)
            if nums:
                max_num = max(int(n) for n in nums)
                # If number looks like it's in thousands (e.g. 120 = $120k)
                if max_num < 1000:
                    return max_num >= min_salary_k
                # If it's a full number (e.g. 120000)
                return max_num >= min_salary_k * 1000
            return True
        df = df[df[salary_col].apply(salary_ok)]
    return df


# ─────────────────────────────────────────────
# JOB TRACKER
# ─────────────────────────────────────────────
def load_tracker():
    if os.path.exists(TRACKER_FILE):
        return pd.read_csv(TRACKER_FILE)
    return pd.DataFrame(columns=["title", "company", "url", "fit_score",
                                  "status", "notes", "saved_at"])


def save_job_to_tracker(job: dict):
    tracker = load_tracker()
    url = job.get("url", "")
    if url and url in tracker["url"].values:
        return tracker, False
    new_row = {
        "title":     job.get("title", ""),
        "company":   job.get("company", ""),
        "url":       url,
        "fit_score": job.get("fit_score", 0),
        "status":    "Saved",
        "notes":     "",
        "saved_at":  datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    tracker = pd.concat([tracker, pd.DataFrame([new_row])], ignore_index=True)
    tracker.to_csv(TRACKER_FILE, index=False)
    return tracker, True


# ─────────────────────────────────────────────
# CLAUDE AI HELPERS
# ─────────────────────────────────────────────
def get_claude_client():
    try:
        import anthropic
    except ImportError:
        st.error("anthropic package not installed. Run: pip install anthropic")
        return None
    api_key = st.session_state.get("anthropic_api_key", "").strip()
    if not api_key:
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def ai_filter_jobs(jobs: list[dict], client) -> list[dict]:
    """Use Claude to re-score each job for real fit vs Eric's background."""
    if not jobs:
        return jobs

    profile_summary = """
Eric Elia – sales leader transitioning into tech/SaaS/fintech/AI.
- 8+ years sales leadership, $5M+ annual gross profit responsibility
- Currently New Car Director at Top 3 Infiniti dealership in the US (Asbury Automotive)
- Led teams of 11–17; ranked #1 Sales Manager in PVR across Andy Mohr Group
- Helped earn 2024 Presidents Award (Courtesy Palm Harbor Honda); Circle of Excellence (Infiniti)
- Marine Corps veteran – Technical Controller / Data Network Specialist
- Target roles: VP Sales, Director of Sales, Head of Sales, Senior AE, Revenue Director
- Target industries: SaaS, fintech, AI, tech, software, cloud, startup
- Remote preferred; open to relocation; Palm Harbor FL
- Hard pass: insurance, commission-only, door-to-door, 1099 gig, entry-level
"""

    jobs_text = ""
    for i, j in enumerate(jobs):
        jobs_text += f"\n--- JOB {i} ---\nTitle: {j.get('title','')}\nCompany: {j.get('company','')}\nDescription: {str(j.get('description', j.get('summary', j.get('details', ''))))[:600]}\n"

    prompt = f"""You are a recruiter helping Eric Elia find the best-fit remote jobs.

ERIC'S PROFILE:
{profile_summary}

JOBS TO EVALUATE (rate each 1–10 for fit):
{jobs_text}

For each job numbered 0 to {len(jobs)-1}, respond with EXACTLY this format (one per line, no extra text):
JOB_INDEX|SCORE|ONE_SENTENCE_REASON

Score 8–10: Strong fit – right title, right industry, right seniority
Score 5–7: Partial fit – some gaps but worth considering
Score 1–4: Poor fit – wrong industry, too junior, commission-only, or filtered out

Return only the numbered lines. Nothing else."""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        lines = response.content[0].text.strip().split("\n")
        for line in lines:
            parts = line.strip().split("|")
            if len(parts) == 3:
                try:
                    idx = int(parts[0].replace("JOB_", "").strip())
                    score = int(parts[1].strip())
                    reason = parts[2].strip()
                    if 0 <= idx < len(jobs):
                        jobs[idx]["ai_score"] = score
                        jobs[idx]["ai_reason"] = reason
                except ValueError:
                    pass
    except Exception as e:
        st.warning(f"AI filtering error: {e}")

    # Add default for any not scored
    for j in jobs:
        if "ai_score" not in j:
            j["ai_score"] = 5
            j["ai_reason"] = "Not evaluated"

    return sorted(jobs, key=lambda x: x["ai_score"], reverse=True)


def generate_resume_bullets(job_title, company, description, client):
    prompt = f"""You are a professional resume writer specialising in sales leadership and career transitions into tech.

Generate 5 powerful, quantified resume bullet points for Eric Elia, tailored to this specific job.

Job Title: {job_title}
Company: {company}
Job Description excerpt:
{description[:1500] if description else "Not provided"}

ERIC'S REAL BACKGROUND & ACHIEVEMENTS (use these specific facts):
- U.S. Marine Corps veteran — Technical Controller / Data Network Specialist (2013–2019)
- 8+ years of sales leadership experience
- $5M+ cumulative annual gross profit responsibility across leadership roles
- Currently: New Car Director at Infiniti of Tampa (Asbury Automotive Group) — Top 3 Infiniti dealership in the US by new car volume, largest in Florida
- Led team of 11 sales professionals at Infiniti of Tampa; qualified dealership for Circle of Excellence
- Previously: Sales Manager at Courtesy Palm Harbor Honda — generated $2M+ annual gross profit, led 17+ associates, helped earn the 2024 Presidents Award
- Previously: Sales Manager at Andy Mohr Honda — generated $3M+ annual gross profit, led 15-person team, ranked #1 Sales Manager in Profit Per Vehicle Retail (PVR) across entire Andy Mohr Group
- Improved conversion rates by optimizing sales pipeline and lead follow-up processes
- Conducted daily sales meetings and performance reviews focused on KPI accountability
- 98% customer satisfaction score as Sales & Leasing Consultant
- Traveled to 33 countries — strong cross-cultural communication and adaptability
- CRM experience: VinSolutions, Eleads, Tekion, Dealertrack, RouteOne, vAuto, CDK Global

Rules for the bullets:
- Start each with a strong action verb (Drove, Led, Grew, Exceeded, Launched, Built, Scaled, etc.)
- Ground every bullet in Eric's REAL achievements above — adapt the framing to fit the job
- Include specific metrics ($2M+, 17 team members, 98% CSAT, #1 ranking, etc.)
- Tailor language and keywords directly to the job description
- Keep each bullet to 1–2 lines
- No generic filler — every word earns its place

Return only the 5 bullets, one per line, each starting with •"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def generate_outreach_message(job_title, company, description, client):
    prompt = f"""Write a short, personalised LinkedIn outreach message from Eric Elia to a recruiter about this role.

Job Title: {job_title}
Company: {company}
Job Description excerpt:
{description[:800] if description else "Not provided"}

ERIC'S REAL STORY (weave in naturally — pick the most relevant detail):
- U.S. Marine Corps veteran turned top sales leader
- 8+ years driving multimillion-dollar revenue — $5M+ in gross profit across roles
- Led teams of up to 17 sales professionals
- Ranked #1 Sales Manager in PVR across the entire Andy Mohr dealer group
- Helped earn the 2024 Presidents Award at Courtesy Palm Harbor Honda
- Currently directing a Top 3 Infiniti dealership in the US — qualified for Circle of Excellence
- Strong background in pipeline management, KPI accountability, and building high-performance teams
- Willing to relocate

Message requirements:
- 3–4 sentences maximum, under 120 words
- Warm and direct — sounds like a real human, not a template
- Reference something specific about the role or company
- Mention 1 specific real achievement from Eric's background
- End with a low-pressure call to action (open to a quick call or chat)
- No buzzwords, no fluff

Return only the message text. No subject line, no signature, no extra commentary."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def generate_cover_letter(job_title, company, description, client):
    prompt = f"""Write a tailored, professional cover letter for Eric Elia applying for this role.

Job Title: {job_title}
Company: {company}
Job Description excerpt:
{description[:1500] if description else "Not provided"}

ERIC'S REAL BACKGROUND (use these specific facts):
- U.S. Marine Corps veteran — Technical Controller / Data Network Specialist (2013–2019)
- 8+ years of sales leadership
- $5M+ cumulative annual gross profit responsibility
- Currently: New Car Director, Infiniti of Tampa — Top 3 Infiniti dealership in US, qualified for Circle of Excellence
- Led team of 11 at Infiniti of Tampa
- Sales Manager at Courtesy Palm Harbor Honda: $2M+ gross profit, 17+ person team, helped earn 2024 Presidents Award
- Sales Manager at Andy Mohr Honda: $3M+ gross profit, 15-person team, ranked #1 in PVR across entire Andy Mohr Group
- 98% customer satisfaction, improved conversion rates through pipeline optimization
- Traveled to 33 countries — cross-cultural communication, adaptability
- Willing to relocate
- Based in Palm Harbor, FL
- Email: ericelia1@gmail.com | Phone: 812-240-7621

Cover letter requirements:
- 3 paragraphs, professional but warm tone
- Paragraph 1: Hook — connect Eric's background to this specific role/company
- Paragraph 2: 2–3 specific achievements that directly map to what the job needs
- Paragraph 3: Brief closing — enthusiasm for the role, call to action
- Under 350 words total
- Do NOT use generic phrases like "I am writing to express my interest"
- Sound like Eric wrote it himself — direct, confident, grounded in real results

Return only the cover letter body (no address block, no "Dear Hiring Manager" header needed — just the 3 paragraphs). No extra commentary."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=700,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def generate_interview_prep(job_title, company, description, client):
    prompt = f"""You are an executive interview coach helping Eric Elia prepare for this job interview.

Job Title: {job_title}
Company: {company}
Job Description:
{description[:2000] if description else "Not provided"}

ERIC'S REAL BACKGROUND:
- U.S. Marine Corps veteran (2013–2019) — Technical Controller / Data Network Specialist
- 8+ years sales leadership; $5M+ annual gross profit responsibility
- New Car Director, Infiniti of Tampa (Asbury Automotive) — Top 3 Infiniti US, qualified Circle of Excellence
- Led 11–17 person sales teams; ranked #1 in PVR across Andy Mohr Group
- Helped earn 2024 Presidents Award at Courtesy Palm Harbor Honda
- 98% CSAT; CRM: VinSolutions, Eleads, Tekion, CDK Global, vAuto
- Traveled to 33 countries; strong cross-cultural communication

Generate interview prep in this exact format:

## 🎯 Key Selling Points for This Role
[3 bullet points — Eric's most relevant strengths for THIS specific job]

## 🔥 Likely Interview Questions + STAR Answers
[5 questions likely for this role, each with a 3–4 sentence STAR-framework answer using Eric's real stories]

## ❓ Smart Questions to Ask the Interviewer
[4 thoughtful questions Eric should ask — shows strategic thinking]

## ⚠️ Potential Concerns & How to Address Them
[2–3 objections an interviewer might raise (e.g., automotive vs tech industry) with brief rebuttals]

Be specific, use Eric's real numbers and stories. No generic advice."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def generate_follow_up_email(job_title, company, description, client):
    prompt = f"""Write a professional follow-up email from Eric Elia after submitting a job application.

Job Title: {job_title}
Company: {company}
Job Description excerpt:
{description[:800] if description else "Not provided"}

ERIC'S BACKGROUND (pick 1–2 most relevant details):
- Marine Corps veteran turned sales leader
- $5M+ annual gross profit; led teams of up to 17
- Ranked #1 Sales Manager in PVR across Andy Mohr Group
- Currently directing a Top 3 US Infiniti dealership
- Helped earn 2024 Presidents Award

Email requirements:
- Subject line included
- 3–4 short paragraphs, under 200 words
- Professional but human — not robotic
- Reference applying for the specific role
- Reinforce 1 standout achievement relevant to this job
- Close with clear next step (happy to schedule a call)
- From: Eric Elia | ericelia1@gmail.com | 812-240-7621

Format:
Subject: [subject line]

[email body]"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


# ─────────────────────────────────────────────
# APP LAYOUT
# ─────────────────────────────────────────────
st.set_page_config(page_title="Eric's AI Job Agent", layout="wide")
st.title("🤖 Eric's AI Job Agent")

# ── Sidebar ──────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    api_key_input = st.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-...",
        help="Required for AI filtering, resume bullets, outreach messages, cover letters, and interview prep.",
    )
    if api_key_input:
        st.session_state["anthropic_api_key"] = api_key_input

    env_key = os.getenv("ANTHROPIC_API_KEY", "")
    if env_key and not api_key_input:
        st.session_state["anthropic_api_key"] = env_key
        st.success("API key loaded from environment ✓")

    st.divider()
    st.header("💰 Salary Filter")
    min_salary = st.slider(
        "Minimum salary ($k/year)",
        min_value=80,
        max_value=300,
        value=100,
        step=10,
        help="Filter out roles that mention salaries below this threshold.",
    )
    st.caption(f"Showing jobs with salary ≥ ${min_salary}k")

    st.divider()
    st.header("🤖 AI Fit Filter")
    use_ai_filter = st.toggle(
        "Use Claude to score fit",
        value=True,
        help="Claude reads each job description and scores how well it fits Eric's background. Slower but much more accurate.",
    )
    min_ai_score = st.slider("Min AI fit score", 1, 10, 6, help="Only show jobs Claude scores at or above this level.")

    st.divider()
    st.header("📊 Tracker Summary")
    tracker_sidebar = load_tracker()
    if len(tracker_sidebar) > 0:
        status_counts = tracker_sidebar["status"].value_counts()
        for status, count in status_counts.items():
            st.write(f"**{status}:** {count}")
        st.caption(f"{len(tracker_sidebar)} total saved jobs")
    else:
        st.caption("No saved jobs yet.")


# ── Tabs ─────────────────────────────────────
tab_search, tab_tracker, tab_interview = st.tabs(["🔍 Find Jobs", "📁 Job Tracker", "🎤 Interview Prep"])


# ══════════════════════════════════════════════
# TAB 1 — FIND JOBS
# ══════════════════════════════════════════════
with tab_search:

    st.markdown("### 👤 Searching based on your profile")
    st.caption(
        f"**{MY_PROFILE['name']}** · {MY_PROFILE['background_summary'][:180]}…"
    )

    # Optional keyword override
    with st.expander("🔧 Override: search by keyword instead"):
        keyword_override = st.text_input(
            "Custom search keyword",
            placeholder="e.g. VP of Sales, Head of Revenue, fintech director",
        )

    # Auto-generate search query from profile
    def build_auto_query():
        titles  = " OR ".join(MY_PROFILE["strong_titles"][:6])
        industries = " ".join(MY_PROFILE["target_industries"][:4])
        return f"{titles} {industries} remote"

    user_input = keyword_override.strip() if keyword_override.strip() else build_auto_query()

    col_search, col_clear = st.columns([2, 1])
    with col_search:
        search_clicked = st.button(
            "🔍 Find Jobs For Me",
            type="primary",
            use_container_width=True,
        )
    with col_clear:
        if st.button("🗑️ Clear results", use_container_width=True):
            for k in ["job_results", "selected_job", "bullets", "outreach",
                      "cover_letter", "follow_up", "interview_prep"]:
                st.session_state.pop(k, None)
            st.rerun()

    if search_clicked or "job_results" in st.session_state:

        if search_clicked:
            with st.spinner("🌐 Fetching latest remote jobs…"):
                try:
                    import sys
                    sys.path.insert(0, BASE_DIR)
                    import main as job_fetcher
                    import importlib
                    importlib.reload(job_fetcher)
                    job_fetcher.main()
                except Exception as e:
                    st.error(f"Error fetching jobs: {e}")
                    st.stop()

        csv_path = os.path.join(BASE_DIR, "remote_jobs.csv")
        if not os.path.exists(csv_path):
            st.error("Could not fetch jobs. Please try again.")
            st.stop()

        raw_df      = pd.read_csv(csv_path)
        scored_df   = score_jobs(raw_df)
        filtered_df = filter_by_query(scored_df, user_input)
        filtered_df = apply_salary_filter(filtered_df, min_salary)
        filtered_df = filtered_df[filtered_df["fit_score"] > 0].head(40)

        if filtered_df.empty:
            st.warning("No jobs found. Try broader keywords like: sales director, VP sales, revenue")
            st.stop()

        # ── AI Fit Filtering ──────────────────
        jobs_list = filtered_df.to_dict("records")

        if use_ai_filter:
            client = get_claude_client()
            if client:
                with st.spinner("🤖 Claude is reading each job and scoring fit for your background…"):
                    jobs_list = ai_filter_jobs(jobs_list, client)
                # Filter by AI score
                jobs_list = [j for j in jobs_list if j.get("ai_score", 0) >= min_ai_score]
            else:
                st.warning("Add your Anthropic API key in the sidebar to enable AI fit filtering.")

        st.markdown(f"### {len(jobs_list)} jobs matching your background")

        if not jobs_list:
            st.warning("No jobs passed the AI fit filter. Try lowering the Min AI fit score in the sidebar.")
            st.stop()

        # ── Job Cards ─────────────────────────
        title_col   = find_text_column(filtered_df, ["title", "job_title", "position"]) or filtered_df.columns[0]
        company_col = find_text_column(filtered_df, ["company", "company_name"])
        desc_col    = find_text_column(filtered_df, ["description", "summary", "details"])
        url_col     = find_text_column(filtered_df, ["url", "link", "job_url"])

        # Store selected job in session state
        if "selected_job" not in st.session_state:
            st.session_state["selected_job"] = None

        for job in jobs_list:
            title   = job.get(title_col, "Unknown Title") if title_col else job.get("title", "Unknown Title")
            company = job.get(company_col, "") if company_col else job.get("company", "")
            url     = job.get(url_col, "") if url_col else job.get("url", "")
            ai_score = job.get("ai_score", "–")
            ai_reason = job.get("ai_reason", "")
            fit_score = int(job.get("fit_score", 0))

            # Color badge by AI score
            if isinstance(ai_score, int):
                if ai_score >= 8:
                    badge = f"🟢 **AI Fit: {ai_score}/10**"
                elif ai_score >= 6:
                    badge = f"🟡 **AI Fit: {ai_score}/10**"
                else:
                    badge = f"🔴 **AI Fit: {ai_score}/10**"
            else:
                badge = f"⬜ Keyword Score: {fit_score}"

            with st.container(border=True):
                col_info, col_actions = st.columns([3, 1])

                with col_info:
                    st.markdown(f"### {title}")
                    if company:
                        st.markdown(f"🏢 **{company}**")
                    st.markdown(badge)
                    if ai_reason:
                        st.caption(f"💡 {ai_reason}")

                with col_actions:
                    if url:
                        st.link_button("🚀 Apply Now", url, use_container_width=True, type="primary")
                    else:
                        st.markdown("*No link available*")

                    job_key = f"{title}_{company}".replace(" ", "_")[:40]

                    if st.button("🎯 Use This Job", key=f"select_{job_key}", use_container_width=True):
                        st.session_state["selected_job"] = job
                        st.session_state.pop("bullets", None)
                        st.session_state.pop("outreach", None)
                        st.session_state.pop("cover_letter", None)
                        st.session_state.pop("follow_up", None)
                        st.session_state.pop("interview_prep", None)
                        st.rerun()

                    if st.button("💾 Save", key=f"save_{job_key}", use_container_width=True):
                        _, was_new = save_job_to_tracker(job)
                        if was_new:
                            st.success("Saved!")
                        else:
                            st.info("Already saved")

        # ── Action Panel for Selected Job ──────
        if st.session_state.get("selected_job"):
            sel = st.session_state["selected_job"]
            sel_title   = sel.get(title_col, sel.get("title", ""))
            sel_company = sel.get(company_col, sel.get("company", "")) if company_col else sel.get("company", "")
            sel_desc    = sel.get(desc_col, sel.get("description", sel.get("summary", ""))) if desc_col else sel.get("description", "")
            sel_url     = sel.get(url_col, sel.get("url", "")) if url_col else sel.get("url", "")

            st.divider()
            st.subheader(f"🎯 Working on: {sel_title} @ {sel_company}")
            if sel_url:
                st.link_button("🚀 Apply Now", sel_url, type="primary")

            col_bullets, col_outreach, col_cover, col_follow = st.columns(4)

            client = get_claude_client()
            if not client:
                st.error("Add your Anthropic API key in the sidebar to generate content.")
            else:
                with col_bullets:
                    if st.button("📝 Resume Bullets", use_container_width=True):
                        with st.spinner("Writing tailored bullets…"):
                            st.session_state["bullets"] = generate_resume_bullets(sel_title, sel_company, sel_desc, client)

                with col_outreach:
                    if st.button("✉️ LinkedIn Outreach", use_container_width=True):
                        with st.spinner("Drafting outreach…"):
                            st.session_state["outreach"] = generate_outreach_message(sel_title, sel_company, sel_desc, client)

                with col_cover:
                    if st.button("📄 Cover Letter", use_container_width=True):
                        with st.spinner("Writing cover letter…"):
                            st.session_state["cover_letter"] = generate_cover_letter(sel_title, sel_company, sel_desc, client)

                with col_follow:
                    if st.button("📬 Follow-Up Email", use_container_width=True):
                        with st.spinner("Drafting follow-up…"):
                            st.session_state["follow_up"] = generate_follow_up_email(sel_title, sel_company, sel_desc, client)

            # Output panels
            for key, label in [
                ("bullets", "📝 Tailored Resume Bullets"),
                ("outreach", "✉️ LinkedIn Outreach Message"),
                ("cover_letter", "📄 Cover Letter"),
                ("follow_up", "📬 Follow-Up Email"),
            ]:
                if key in st.session_state:
                    st.subheader(label)
                    st.markdown(st.session_state[key])
                    st.code(st.session_state[key], language=None)
                    if st.button(f"Clear {label.split()[-1].lower()}", key=f"clear_{key}"):
                        del st.session_state[key]


# ══════════════════════════════════════════════
# TAB 2 — JOB TRACKER
# ══════════════════════════════════════════════
with tab_tracker:
    st.subheader("📁 Your Saved Jobs")
    tracker_df = load_tracker()

    if tracker_df.empty:
        st.info("No saved jobs yet. Use the Find Jobs tab to search and save roles.")
    else:
        st.caption("Edit status or notes directly in the table, then click Save Changes.")
        edited_tracker = st.data_editor(
            tracker_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["Saved", "Applied", "Phone Screen", "Interview", "Offer", "Rejected", "Passed"],
                    required=True,
                ),
                "url": st.column_config.LinkColumn("Job URL"),
                "notes": st.column_config.TextColumn("Notes", width="large"),
                "fit_score": st.column_config.NumberColumn("Score", format="%d"),
            },
        )

        col_save_tracker, col_export = st.columns(2)

        with col_save_tracker:
            if st.button("💾 Save Changes", use_container_width=True):
                edited_tracker.to_csv(TRACKER_FILE, index=False)
                st.success("Tracker saved!")

        with col_export:
            csv_bytes = edited_tracker.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export as CSV",
                data=csv_bytes,
                file_name="saved_jobs.csv",
                mime="text/csv",
                use_container_width=True,
            )


# ══════════════════════════════════════════════
# TAB 3 — INTERVIEW PREP
# ══════════════════════════════════════════════
with tab_interview:
    st.subheader("🎤 Interview Preparation")

    sel_job = st.session_state.get("selected_job")

    if sel_job:
        title_col_i   = find_text_column(pd.DataFrame([sel_job]), ["title", "job_title", "position"])
        company_col_i = find_text_column(pd.DataFrame([sel_job]), ["company", "company_name"])
        desc_col_i    = find_text_column(pd.DataFrame([sel_job]), ["description", "summary", "details"])

        sel_title_i   = sel_job.get(title_col_i, sel_job.get("title", "")) if title_col_i else sel_job.get("title", "")
        sel_company_i = sel_job.get(company_col_i, sel_job.get("company", "")) if company_col_i else sel_job.get("company", "")
        sel_desc_i    = sel_job.get(desc_col_i, sel_job.get("description", "")) if desc_col_i else sel_job.get("description", "")

        st.info(f"Preparing for: **{sel_title_i}** at **{sel_company_i}**")
        st.caption("Selected from Find Jobs tab. Go back to Find Jobs and click '🎯 Use This Job' to change.")
    else:
        st.info("No job selected yet. Go to **Find Jobs**, search, and click **🎯 Use This Job** on any listing.")
        st.subheader("Or prep for a custom role:")

    # Manual entry always available
    with st.expander("✏️ Enter job details manually" if sel_job else "Enter job details", expanded=not sel_job):
        manual_title   = st.text_input("Job title", value=sel_title_i if sel_job else "")
        manual_company = st.text_input("Company", value=sel_company_i if sel_job else "")
        manual_desc    = st.text_area("Paste the job description", value=sel_desc_i if sel_job else "", height=200)
        use_manual = st.button("Use these details for interview prep")
        if use_manual:
            st.session_state["interview_manual"] = {
                "title": manual_title,
                "company": manual_company,
                "description": manual_desc,
            }

    # Determine which details to use
    if st.session_state.get("interview_manual"):
        prep_title   = st.session_state["interview_manual"]["title"]
        prep_company = st.session_state["interview_manual"]["company"]
        prep_desc    = st.session_state["interview_manual"]["description"]
    elif sel_job:
        prep_title, prep_company, prep_desc = sel_title_i, sel_company_i, sel_desc_i
    else:
        prep_title = prep_company = prep_desc = ""

    if prep_title:
        client = get_claude_client()
        if not client:
            st.error("Add your Anthropic API key in the sidebar to generate interview prep.")
        elif st.button("🎤 Generate Interview Prep", type="primary", use_container_width=True):
            with st.spinner("Claude is building your interview prep pack…"):
                st.session_state["interview_prep"] = generate_interview_prep(prep_title, prep_company, prep_desc, client)

        if "interview_prep" in st.session_state:
            st.divider()
            st.markdown(st.session_state["interview_prep"])
            st.divider()
            st.download_button(
                "⬇️ Download Interview Prep",
                data=st.session_state["interview_prep"],
                file_name=f"interview_prep_{prep_title.replace(' ', '_')}.md",
                mime="text/markdown",
                use_container_width=True,
            )
            if st.button("Clear interview prep"):
                del st.session_state["interview_prep"]
