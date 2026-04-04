import streamlit as st
import pandas as pd
import subprocess
import os
from datetime import datetime

# Always work relative to the folder this script lives in
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRACKER_FILE = os.path.join(BASE_DIR, "saved_jobs.csv")

# ─────────────────────────────────────────────
# ERIC'S PROFILE  (edit this to update scoring)
# ─────────────────────────────────────────────
MY_PROFILE = {
    "name": "Eric",
    "background_summary": (
        "Sales leadership professional with experience in SaaS, fintech, and AI. "
        "Specialises in revenue growth, team leadership, account management, and "
        "business development."
    ),
    "strong_titles": [
        "sales manager", "new car director", "account executive",
        "business development manager", "customer success manager",
        "partnerships manager", "revenue operations manager", "growth manager",
        "vp of sales", "director of sales", "head of sales",
        "senior account executive", "regional sales manager",
    ],
    "seniority_terms": [
        "director", "vp", "vice president", "head of", "senior", "manager", "lead",
    ],
    "target_industries": ["saas", "fintech", "ai", "startup", "tech"],
    "salary_signals": ["$", "ote", "equity", "base salary", "compensation", "k/year", "usd"],
    "strong_keywords": [
        "sales", "revenue", "leadership", "account management",
        "business development", "customer success", "partnerships",
        "saas", "fintech", "ai", "startup", "remote",
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
    title_col  = find_text_column(df, ["title", "job_title", "position"])
    company_col = find_text_column(df, ["company", "company_name"])
    desc_col   = find_text_column(df, ["description", "summary", "details"])
    salary_col = find_text_column(df, ["salary", "compensation", "pay", "salary_range"])

    if title_col is None:
        st.error("Couldn't find a title column in remote_jobs.csv.")
        return df

    searchable = df[title_col].fillna("").astype(str)
    if company_col:
        searchable = searchable + " " + df[company_col].fillna("").astype(str)
    if desc_col:
        searchable = searchable + " " + df[desc_col].fillna("").astype(str)

    score = pd.Series(0, index=df.index)

    # Title match  (+3 each)
    for title in MY_PROFILE["strong_titles"]:
        score += searchable.str.contains(title, case=False, na=False).astype(int) * 3

    # Seniority signals  (+2 each)
    for term in MY_PROFILE["seniority_terms"]:
        score += searchable.str.contains(term, case=False, na=False).astype(int) * 2

    # Industry fit  (+2 each)
    for industry in MY_PROFILE["target_industries"]:
        score += searchable.str.contains(industry, case=False, na=False).astype(int) * 2

    # General keyword match  (+1 each)
    for kw in MY_PROFILE["strong_keywords"]:
        score += searchable.str.contains(kw, case=False, na=False).astype(int)

    # Salary signals in description  (+1 each)
    for sig in MY_PROFILE["salary_signals"]:
        score += searchable.str.contains(sig, case=False, na=False).astype(int)

    # Salary column present and non-empty  (+2)
    if salary_col:
        score += df[salary_col].notna().astype(int) * 2

    # Negatives  (−5 each)
    for bad in MY_PROFILE["negative_keywords"]:
        score -= searchable.str.contains(bad, case=False, na=False).astype(int) * 5

    result = df.copy()
    result["fit_score"] = score
    return result.sort_values("fit_score", ascending=False)


def filter_by_query(df, query):
    title_col  = find_text_column(df, ["title", "job_title", "position"])
    company_col = find_text_column(df, ["company", "company_name"])
    desc_col   = find_text_column(df, ["description", "summary", "details"])

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
    # Avoid duplicates by url
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


def generate_resume_bullets(job_title, company, description, client):
    prompt = f"""You are a professional resume writer specialising in sales and business leadership.

Generate 5 powerful, quantified resume bullet points for Eric tailored to this specific job.

Job Title: {job_title}
Company: {company}
Job Description excerpt:
{description[:1500] if description else "Not provided"}

Eric's background:
- Sales leadership in SaaS, fintech, and AI industries
- Revenue growth, quota attainment, and team leadership
- Account management, business development, and customer success
- Experience managing and building high-performing sales teams

Rules for the bullets:
- Start each with a strong action verb (Drove, Led, Grew, Exceeded, Launched, etc.)
- Include realistic metrics or percentages where plausible (e.g., "grew ARR by 40%")
- Tailor language to keywords in the job description
- Keep each bullet to 1–2 lines
- No generic filler — every word should earn its place

Return only the 5 bullets, one per line, each starting with •"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def generate_outreach_message(job_title, company, description, client):
    prompt = f"""Write a short, personalised LinkedIn outreach message from Eric to a recruiter about this role.

Job Title: {job_title}
Company: {company}
Job Description excerpt:
{description[:800] if description else "Not provided"}

Eric's background:
- Sales leadership professional in SaaS, fintech, and AI
- Strong track record in revenue growth, team building, and business development

Message requirements:
- 3–4 sentences maximum, under 120 words
- Warm and direct — not robotic or overly formal
- Reference something specific about the role or company
- Mention 1 relevant achievement or background point
- End with a clear, low-pressure call to action (e.g., open to a quick call)
- Sound like a real person wrote it

Return only the message text, no subject line, no extra commentary."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=400,
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
        help="Required for resume bullets and outreach messages.",
    )
    if api_key_input:
        st.session_state["anthropic_api_key"] = api_key_input

    env_key = os.getenv("ANTHROPIC_API_KEY", "")
    if env_key and not api_key_input:
        st.session_state["anthropic_api_key"] = env_key
        st.success("API key loaded from environment ✓")

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
tab_search, tab_tracker = st.tabs(["🔍 Find Jobs", "📁 Job Tracker"])


# ══════════════════════════════════════════════
# TAB 1 — FIND JOBS
# ══════════════════════════════════════════════
with tab_search:
    user_input = st.text_input(
        "What job are you looking for?",
        placeholder="e.g. sales manager, account executive, fintech, customer success",
    )

    if user_input:
        with st.spinner("Fetching latest jobs from the web…"):
            subprocess.run(["python3", os.path.join(BASE_DIR, "main.py")], cwd=BASE_DIR, check=False)

        csv_path = os.path.join(BASE_DIR, "remote_jobs.csv")
        if not os.path.exists(csv_path):
            st.error("remote_jobs.csv not found. Check that main.py ran correctly.")
            st.stop()

        raw_df = pd.read_csv(csv_path)
        scored_df = score_jobs(raw_df)
        filtered_df = filter_by_query(scored_df, user_input)
        filtered_df = filtered_df[filtered_df["fit_score"] > 0].head(30)

        st.markdown(f"### {len(filtered_df)} matching jobs")

        if filtered_df.empty:
            st.warning("No jobs found. Try broader keywords like: sales, account executive, revenue")
        else:
            display_cols = [c for c in ["title", "company", "location", "fit_score", "url"]
                            if c in filtered_df.columns]
            st.dataframe(filtered_df[display_cols], use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("🎯 Take action on a job")

            # Build dropdown labels
            title_col   = find_text_column(filtered_df, ["title", "job_title", "position"]) or filtered_df.columns[0]
            company_col = find_text_column(filtered_df, ["company", "company_name"])

            def make_label(i, row):
                title   = row.get(title_col, "Unknown Title")
                company = row.get(company_col, "Unknown Company") if company_col else "Unknown Company"
                score   = int(row.get("fit_score", 0))
                return f"[Score {score}]  {title}  @  {company}"

            options_labels = [make_label(i, row) for i, (_, row) in enumerate(filtered_df.iterrows())]
            selected_label = st.selectbox("Select a job:", options_labels)
            selected_idx   = options_labels.index(selected_label)
            selected_job   = filtered_df.iloc[selected_idx].to_dict()

            desc_col = find_text_column(filtered_df, ["description", "summary", "details"])
            job_description = selected_job.get(desc_col, "") if desc_col else ""

            # Show job URL if available
            url_col = find_text_column(filtered_df, ["url", "link", "job_url"])
            if url_col and selected_job.get(url_col):
                st.markdown(f"🔗 [View job posting]({selected_job[url_col]})")

            st.divider()

            col_save, col_bullets, col_outreach = st.columns(3)

            # ── Save Job ──────────────────────────
            with col_save:
                if st.button("💾 Save to Tracker", use_container_width=True):
                    _, was_new = save_job_to_tracker(selected_job)
                    if was_new:
                        st.success("✅ Job saved!")
                    else:
                        st.info("Already in your tracker.")

            # ── Resume Bullets ────────────────────
            with col_bullets:
                if st.button("📝 Resume Bullets", use_container_width=True):
                    client = get_claude_client()
                    if not client:
                        st.error("Add your Anthropic API key in the sidebar first.")
                    else:
                        with st.spinner("Writing bullets with Claude…"):
                            bullets = generate_resume_bullets(
                                selected_job.get(title_col, ""),
                                selected_job.get(company_col, "") if company_col else "",
                                job_description,
                                client,
                            )
                        st.session_state["bullets"] = bullets

            # ── Outreach Message ──────────────────
            with col_outreach:
                if st.button("✉️ Outreach Message", use_container_width=True):
                    client = get_claude_client()
                    if not client:
                        st.error("Add your Anthropic API key in the sidebar first.")
                    else:
                        with st.spinner("Drafting message with Claude…"):
                            message = generate_outreach_message(
                                selected_job.get(title_col, ""),
                                selected_job.get(company_col, "") if company_col else "",
                                job_description,
                                client,
                            )
                        st.session_state["outreach"] = message

            # ── Output panels ─────────────────────
            if "bullets" in st.session_state:
                st.subheader("📝 Tailored Resume Bullets")
                st.markdown(st.session_state["bullets"])
                st.code(st.session_state["bullets"], language=None)
                if st.button("Clear bullets"):
                    del st.session_state["bullets"]

            if "outreach" in st.session_state:
                st.subheader("✉️ Recruiter Outreach Message")
                st.markdown(st.session_state["outreach"])
                st.code(st.session_state["outreach"], language=None)
                if st.button("Clear message"):
                    del st.session_state["outreach"]


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
