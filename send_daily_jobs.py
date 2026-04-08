"""
send_daily_jobs.py
Runs via GitHub Actions every morning.
Fetches jobs, AI-scores them, emails Eric the top 20.
"""

import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
import pandas as pd

# ── Import the fetcher ────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main as job_fetcher

PROFILE_SUMMARY = """
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

TARGET_GOOD_JOBS = 20
MIN_AI_SCORE = 7


def ai_score_jobs(jobs: list, client) -> list:
    """Score jobs in batches of 25, return all with ai_score added."""
    batch_size = 25
    for batch_start in range(0, len(jobs), batch_size):
        batch = jobs[batch_start:batch_start + batch_size]
        batch_text = ""
        for i, j in enumerate(batch):
            idx = batch_start + i
            desc = str(j.get("description", j.get("summary", "")))[:500]
            batch_text += f"\n--- JOB {idx} ---\nTitle: {j.get('title','')}\nCompany: {j.get('company','')}\nDescription: {desc}\n"

        prompt = f"""You are a recruiter helping Eric Elia find the best-fit remote jobs.

ERIC'S PROFILE:
{PROFILE_SUMMARY}

JOBS TO EVALUATE:
{batch_text}

For each job numbered {batch_start} to {batch_start + len(batch) - 1}, respond with EXACTLY:
JOB_INDEX|SCORE|ONE_SENTENCE_REASON

Score 8–10: Strong fit – right title, right industry, right seniority
Score 5–7: Partial fit – some gaps but worth considering
Score 1–4: Poor fit – wrong role, too junior, commission-only, irrelevant

Return only the numbered lines. Nothing else."""

        try:
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            for line in response.content[0].text.strip().split("\n"):
                parts = line.strip().split("|")
                if len(parts) == 3:
                    try:
                        idx = int(parts[0].replace("JOB_", "").strip())
                        score = int(parts[1].strip())
                        if 0 <= idx < len(jobs):
                            jobs[idx]["ai_score"] = score
                            jobs[idx]["ai_reason"] = parts[2].strip()
                    except ValueError:
                        pass
        except Exception as e:
            print(f"AI scoring error on batch {batch_start}: {e}")

    # Default unscored
    for j in jobs:
        if "ai_score" not in j:
            j["ai_score"] = 0
            j["ai_reason"] = "Not scored"

    return sorted(jobs, key=lambda x: x["ai_score"], reverse=True)


def build_email_html(good_jobs: list) -> str:
    rows = ""
    for i, job in enumerate(good_jobs, 1):
        score = job.get("ai_score", "–")
        if score >= 9:
            badge = f'<span style="background:#22c55e;color:white;padding:2px 8px;border-radius:12px;font-size:12px;">🟢 {score}/10</span>'
        elif score >= 7:
            badge = f'<span style="background:#eab308;color:white;padding:2px 8px;border-radius:12px;font-size:12px;">🟡 {score}/10</span>'
        else:
            badge = f'<span style="background:#ef4444;color:white;padding:2px 8px;border-radius:12px;font-size:12px;">🔴 {score}/10</span>'

        url = job.get("url", "#")
        rows += f"""
        <tr style="border-bottom:1px solid #e5e7eb;">
          <td style="padding:16px 8px;font-size:13px;color:#6b7280;">{i}</td>
          <td style="padding:16px 8px;">
            <div style="font-weight:600;font-size:15px;">{job.get('title','')}</div>
            <div style="color:#6b7280;font-size:13px;">🏢 {job.get('company','')}</div>
            <div style="color:#9ca3af;font-size:12px;margin-top:4px;">💡 {job.get('ai_reason','')}</div>
          </td>
          <td style="padding:16px 8px;">{badge}</td>
          <td style="padding:16px 8px;">
            <a href="{url}" style="background:#3b82f6;color:white;padding:8px 16px;border-radius:6px;text-decoration:none;font-size:13px;font-weight:600;">Apply →</a>
          </td>
        </tr>"""

    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f9fafb;margin:0;padding:20px;">
  <div style="max-width:700px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
    <div style="background:linear-gradient(135deg,#1e40af,#3b82f6);padding:32px;text-align:center;">
      <h1 style="color:white;margin:0;font-size:24px;">🤖 Eric's Daily Job Digest</h1>
      <p style="color:#bfdbfe;margin:8px 0 0;">Top {len(good_jobs)} jobs matching your background — good morning!</p>
    </div>
    <div style="padding:24px;">
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:#f3f4f6;">
            <th style="padding:12px 8px;text-align:left;font-size:12px;color:#6b7280;">#</th>
            <th style="padding:12px 8px;text-align:left;font-size:12px;color:#6b7280;">JOB</th>
            <th style="padding:12px 8px;text-align:left;font-size:12px;color:#6b7280;">AI FIT</th>
            <th style="padding:12px 8px;text-align:left;font-size:12px;color:#6b7280;">ACTION</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <div style="background:#f9fafb;padding:20px;text-align:center;color:#9ca3af;font-size:12px;">
      Generated by Eric's AI Job Agent · <a href="https://eric-job-agent.streamlit.app" style="color:#3b82f6;">Open Full App</a>
    </div>
  </div>
</body>
</html>"""


def send_email(html: str, job_count: int):
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    to_email = os.environ.get("TO_EMAIL", gmail_address)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🤖 {job_count} New Jobs For You Today"
    msg["From"] = gmail_address
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_password)
        server.sendmail(gmail_address, to_email, msg.as_string())

    print(f"Email sent to {to_email} with {job_count} jobs.")


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print("Fetching jobs...")
    job_fetcher.main()

    csv_path = job_fetcher.OUTPUT_CSV
    df = pd.read_csv(csv_path)
    jobs = df.to_dict("records")
    print(f"Loaded {len(jobs)} jobs from CSV.")

    print("AI scoring jobs...")
    scored = ai_score_jobs(jobs, client)

    good_jobs = [j for j in scored if j.get("ai_score", 0) >= MIN_AI_SCORE]
    good_jobs = good_jobs[:TARGET_GOOD_JOBS]
    print(f"Found {len(good_jobs)} jobs scoring {MIN_AI_SCORE}+.")

    if not good_jobs:
        print("No good jobs today — skipping email.")
        return

    html = build_email_html(good_jobs)
    send_email(html, len(good_jobs))


if __name__ == "__main__":
    main()
