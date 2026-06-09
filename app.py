import json
import sys
import time
import tempfile
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# Imports from your src
from src.extractor import ResumeExtractor
from src.scorer import ScoringWeights
from src.screener import ResumeScreener
from src.utils import (
    setup_logging, format_duration, estimate_tokens
)

st.set_page_config(page_title="CalibrHire", page_icon="🎯", layout="wide")

# ─────────────────────────── Enhanced CSS ─────────────────────────────
st.markdown("""
<style>
    .main { background-color: #f8fafc; }
    .stApp { background: #f8fafc; }
    .header-card { 
        background: linear-gradient(135deg, #1e293b, #334155); 
        padding: 2.5rem; border-radius: 16px; color: white; 
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); margin-bottom: 20px;
    }
    .metric-card { 
        background: white; border-radius: 12px; padding: 1.5rem; 
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border-left: 5px solid #3b82f6;
    }
    .gemini-badge {
        background: linear-gradient(135deg, #4285f4, #34a853); color: white; 
        padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600;
    }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────── Session state ──────────────────────────
if "session_results" not in st.session_state: st.session_state.session_results = None
if "history" not in st.session_state: st.session_state.history = []
if "load_samples" not in st.session_state: st.session_state.load_samples = False

# Header
st.markdown('<div class="header-card"><h1>🎯 CalibrHire</h1><p>AI-Powered Talent Intelligence Platform</p></div>', unsafe_allow_html=True)

# ═══════════════════════════ SIDEBAR ════════════════════════════════
with st.sidebar:
    st.header("⚙️ Configuration")
    provider = st.selectbox("AI Provider", ["Google Gemini (FREE ✅)", "Anthropic (Claude)", "OpenAI (GPT)"])
    
    if "Gemini" in provider:
        prov_key = "gemini"
        st.markdown('<div class="gemini-badge">🆓 Free Tier</div>', unsafe_allow_html=True)
    else:
        prov_key = "api"

    api_key = st.text_input("API Key", type="password", help="Your AI provider API key.")
    model_override = st.text_input("Model (optional)", placeholder="e.g. gemini-1.5-flash")

    st.divider()
    st.subheader("🎚️ Scoring Weights")
    w_skills = st.slider("Skills Match", 0, 100, 40)
    w_exp = st.slider("Experience", 0, 100, 30)
    w_edu = st.slider("Education", 0, 100, 15)
    w_culture = st.slider("Cultural Fit", 0, 100, 15)
    
    total_w = w_skills + w_exp + w_edu + w_culture
    st.divider()
    if st.button("Generate sample resumes", use_container_width=True):
        st.session_state.load_samples = True

# ═══════════════════════════ MAIN TABS ══════════════════════════════
tab_screen, tab_results, tab_history = st.tabs(["📋 Screen Resumes", "📊 Results", "🗂️ History"])

# ──────────────────── TAB 1: Screen Resumes ─────────────────────────
with tab_screen:
    col_jd, col_up = st.columns([1, 1], gap="large")

    with col_jd:
        st.subheader("📝 Job Description")
        sample_jd = ""
        if st.session_state.get("load_samples"):
            sample_jd = """Senior Python Developer
Platform Team | Full-time | Remote / Hybrid

About the role
We are looking for an experienced Senior Python Developer to join our platform team and drive the development of scalable, high-performance backend systems. You will play a key role in architecting microservices, optimizing infrastructure, and collaborating with cross-functional teams to deliver reliable products.

Responsibilities
- Design, build, and maintain robust Python-based backend services and APIs
- Develop and optimize RESTful services using FastAPI or Django REST Framework
- Manage and scale PostgreSQL and Redis databases for high-availability systems
- Containerize and orchestrate applications using Docker and Kubernetes
- Deploy, monitor, and maintain cloud infrastructure on AWS (EC2, RDS, S3, Lambda)
- Build and maintain CI/CD pipelines using GitHub Actions or Jenkins
- Contribute to microservices architecture decisions and best practices
- Collaborate with frontend, DevOps, and product teams in an Agile environment

Required skills
Python, FastAPI, Django REST Framework, PostgreSQL, Redis, Docker, Kubernetes, AWS, GitHub Actions, Jenkins, Microservices, CI/CD

Requirements
- 5+ years of professional Python development experience
- Strong understanding of distributed systems and backend architecture
- Proficiency in containerization and cloud deployment workflows
- Solid problem-solving skills with clear written and verbal communication
- Bachelor's or Master's degree in Computer Science or equivalent

Nice to have
- Open-source contributions (GitHub portfolio appreciated)
- Hands-on experience with ML/AI frameworks such as PyTorch or TensorFlow
- Familiarity with observability tools (Prometheus, Grafana, ELK stack)

Why join us
- Work on high-scale, real-world distributed systems
- Flexible hybrid/remote work environment
- Collaborative, engineering-first culture
- Opportunities for growth into tech lead or architect roles"""

        job_description = st.text_area(
            "Paste the job description here",
            value=sample_jd,
            height=350,
            placeholder="Paste or type the full job description…",
        )
        if job_description:
            st.caption(f"📏 ~{estimate_tokens(job_description)} tokens")

    with col_up:
        st.subheader("📂 Upload Resumes")
        uploaded_files = st.file_uploader(
            "Choose resume files (PDF, DOCX, TXT)",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True,
        )
        if uploaded_files:
            st.success(f"✅ {len(uploaded_files)} file(s) ready")
            for f in uploaded_files:
                st.caption(f"• {f.name} ({len(f.getvalue())/1024:.1f} KB)")

        if st.session_state.get("load_samples"):
            st.info("💡 Sample resumes loaded — click **Start Screening** to test.")
            st.session_state.load_samples = False

    st.divider()

    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        start_btn = st.button(
            "🚀 Start Screening",
            use_container_width=True,
            type="primary",
            disabled=not (job_description),
        )
    with col_info:
        if not job_description:
            st.warning("Add a job description to continue.")

    # ── Run screening ────────────────────────────────────────────────
    if start_btn:
        if not job_description.strip():
            st.error("Job description is required.")
            st.stop()

        texts: dict = {}
        extractor = ResumeExtractor()

        if uploaded_files:
            for uf in uploaded_files:
                try:
                    # Windows-safe temp path
                    tmp = Path(tempfile.gettempdir()) / uf.name
                    tmp.write_bytes(uf.getvalue())
                    texts[uf.name] = extractor.extract(tmp)
                    tmp.unlink(missing_ok=True)
                except Exception as e:
                    st.warning(f"⚠️ Could not extract '{uf.name}': {e}")

        if not texts:
            # Built-in sample resumes for demo / testing
            texts = {
                "alice_chen_senior.txt": """Alice Chen | alice@email.com
Senior Software Engineer — 7 years experience

EXPERIENCE
Lead Python Developer @ TechCorp (2020-Present)
- Architected microservices platform using FastAPI + Kubernetes, 2M req/day
- Led team of 6, cut deployment time 60% via GitHub Actions CI/CD
- Tech: Python, FastAPI, PostgreSQL, Redis, Docker, K8s, AWS

Senior Python Developer @ DataFlow Inc (2018-2020)
- Real-time ETL pipelines with Apache Kafka + Python
- ML model serving with TensorFlow + FastAPI

SKILLS: Python, FastAPI, Django REST, PostgreSQL, Redis, Docker, Kubernetes,
AWS, GitHub Actions, Jenkins, TensorFlow, PyTorch

EDUCATION: M.Sc. Computer Science — Stanford University (2017)
OPEN SOURCE: Contributor to FastAPI, 3 published PyPI packages""",

                "bob_martinez_mid.txt": """Bob Martinez | bob.m@gmail.com
Python Developer — 3 years

EXPERIENCE
Python Developer @ Webagency (2022-Present)
- REST APIs with Django REST Framework
- PostgreSQL database design
- Basic Docker, AWS S3

SKILLS: Python, Django REST, PostgreSQL, Docker (basic), Git, AWS S3

EDUCATION: B.Sc. Information Technology — State University (2021)
Note: No Kubernetes or CI/CD pipeline experience.""",

                "carol_johnson_junior.txt": """Carol Johnson | carol@mail.com
Junior Developer — 1 year experience

EXPERIENCE
Junior Developer @ SmallBiz (2023-Present)
- Maintained legacy PHP website
- Basic Python scripts for data cleanup

SKILLS: Python (beginner), PHP, HTML, CSS, Git, MySQL

EDUCATION: B.A. Business Administration — Community College (2023)
Certifications: Python Basics (Coursera 2023)""",
            }

        weights = ScoringWeights(
            skills=w_skills / total_w,
            experience=w_exp / total_w,
            education=w_edu / total_w,
            cultural_fit=w_culture / total_w,
        )

        screener = ResumeScreener(
            api_key=api_key if api_key else "mock_key",
            provider=prov_key,
            model=model_override or None,
            weights=weights,
        )

        progress_bar = st.progress(0, text="Initialising…")
        status_text  = st.empty()
        start_time   = time.time()

        def update_progress(current, total, filename):
            pct = current / total if total else 0
            progress_bar.progress(pct, text=f"Processing {current}/{total}: {filename}")
            status_text.caption(f"⏱ Elapsed: {format_duration(time.time() - start_time)}")

        with st.spinner("Scoring resumes with AI…"):
            session = screener.screen_texts(
                texts=texts,
                job_description=job_description,
                progress_callback=update_progress,
            )

        progress_bar.progress(1.0, text="✅ Screening complete!")
        status_text.empty()

        st.session_state.session_results = session
        st.session_state.history.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M"),
            "provider": prov_key,
            "resumes": len(session.results),
            "elapsed_sec": round(session.elapsed_seconds, 1),
            "tokens_used": session.total_tokens,
        })

        st.success(
            f"🎉 Screened {len(session.results)} resume(s) in "
            f"{format_duration(session.elapsed_seconds)} · "
            f"{session.total_tokens:,} tokens used"
        )
        st.info("Go to the **Results** tab to view rankings.")


# ──────────────────── TAB 2: Results ────────────────────────────────
with tab_results:
    session = st.session_state.session_results

    if session is None:
        st.info("Run a screening session to see results here.")
    else:
        ranked = session.ranked

        # Summary metric cards
        mc = st.columns(4)
        counts = {"Strong Yes": 0, "Yes": 0, "Maybe": 0, "No": 0}
        for r in ranked:
            counts[r.recommendation] = counts.get(r.recommendation, 0) + 1

        colours = ["#10b981", "#3b82f6", "#f59e0b", "#ef4444"]
        for col, (label, colour) in zip(mc, zip(counts.keys(), colours)):
            with col:
                st.markdown(f"""
                <div class="metric-card">
                  <div class="value" style="color:{colour}">{counts[label]}</div>
                  <div class="label">{label}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Score bar chart
        if ranked:
            colour_map = {
                "Strong Yes": "#10b981", "Yes": "#3b82f6",
                "Maybe": "#f59e0b", "No": "#ef4444",
            }
            fig = go.Figure(go.Bar(
                x=[r.overall_score for r in ranked],
                y=[r.filename[:30] for r in ranked],
                orientation="h",
                marker_color=[colour_map.get(r.recommendation, "#6b7280") for r in ranked],
                text=[f"{r.overall_score:.1f}" for r in ranked],
                textposition="outside",
            ))
            fig.update_layout(
                xaxis=dict(range=[0, 115], title="Score (0–100)"),
                yaxis=dict(autorange="reversed"),
                height=max(250, len(ranked) * 55 + 80),
                margin=dict(l=0, r=50, t=30, b=30),
                plot_bgcolor="white", paper_bgcolor="white",
            )
            fig.add_vline(x=80, line_dash="dot", line_color="#10b981", annotation_text="Strong Yes ≥80")
            fig.add_vline(x=65, line_dash="dot", line_color="#3b82f6", annotation_text="Yes ≥65")
            fig.add_vline(x=45, line_dash="dot", line_color="#f59e0b", annotation_text="Maybe ≥45")
            st.plotly_chart(fig, use_container_width=True)

        # Results table
        st.subheader("📋 Ranked Candidates")
        rows = []
        for rank, r in enumerate(ranked, 1):
            rows.append({
                "Rank": rank,
                "Filename": r.filename,
                "Score": r.overall_score,
                "Recommendation": r.recommendation,
                "Experience (yrs)": r.years_of_experience,
                "Education": r.education_level,
                "Matched Skills": len(r.matched_skills),
                "Missing Skills": len(r.missing_skills),
            })
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(
                df, use_container_width=True, hide_index=True,
                column_config={
                    "Score": st.column_config.ProgressColumn(
                        "Score", min_value=0, max_value=100, format="%.1f"
                    ),
                },
            )

        # Candidate detail expanders
        st.subheader("🔎 Candidate Details")
        for rank, r in enumerate(ranked, 1):
            with st.expander(f"#{rank} · {r.filename}  —  Score: {r.overall_score:.1f}  · {r.recommendation}"):
                if r.error:
                    st.error(f"Error: {r.error}")
                    continue

                dcol1, dcol2 = st.columns(2)
                with dcol1:
                    st.markdown("**📊 Dimension Scores**")
                    for dim, score in [
                        ("Skills", r.skills_score),
                        ("Experience", r.experience_score),
                        ("Education", r.education_score),
                        ("Cultural Fit", r.cultural_fit_score),
                    ]:
                        st.metric(dim, f"{score:.0f}/100")

                with dcol2:
                    st.markdown("**👤 Candidate Info**")
                    st.write(f"**Experience:** {r.years_of_experience} years")
                    st.write(f"**Education:** {r.education_level or 'Not specified'}")
                    if r.matched_skills:
                        st.write(f"**✅ Matched:** {', '.join(r.matched_skills[:5])}")
                    if r.missing_skills:
                        st.write(f"**❌ Missing:** {', '.join(r.missing_skills[:5])}")

                st.markdown("**📝 Summary**")
                st.info(r.summary)
                st.markdown("**⚖️ Justification**")
                st.warning(r.justification)

                # Radar chart
                cats = ["Skills", "Experience", "Education", "Cultural Fit"]
                vals = [r.skills_score, r.experience_score, r.education_score, r.cultural_fit_score]
                fig_r = go.Figure(go.Scatterpolar(
                    r=vals + [vals[0]], theta=cats + [cats[0]],
                    fill="toself", fillcolor="rgba(48,43,99,.2)",
                    line_color="#302b63",
                ))
                fig_r.update_layout(
                    polar=dict(radialaxis=dict(range=[0, 100])),
                    height=280, margin=dict(l=40, r=40, t=30, b=30),
                    paper_bgcolor="white",
                )
                st.plotly_chart(fig_r, use_container_width=True)

        # Export
        st.divider()
        if ranked:
            from io import StringIO
            import csv as csv_mod

            buf = StringIO()
            fieldnames = [
                "rank", "filename", "overall_score", "recommendation",
                "years_of_experience", "education_level",
                "skills_score", "experience_score", "education_score",
                "cultural_fit_score", "matched_skills", "missing_skills",
                "summary", "justification",
            ]
            writer = csv_mod.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for rank, r in enumerate(ranked, 1):
                row = r.to_dict()
                row["rank"] = rank
                row["matched_skills"] = ", ".join(row.get("matched_skills") or [])
                row["missing_skills"]  = ", ".join(row.get("missing_skills")  or [])
                writer.writerow(row)

            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "⬇️ Download CSV", data=buf.getvalue(),
                    file_name="screening_results.csv", mime="text/csv",
                    use_container_width=True,
                )
            with c2:
                st.download_button(
                    "⬇️ Download JSON",
                    data=json.dumps({"results": [r.to_dict() for r in ranked]}, indent=2),
                    file_name="screening_results.json", mime="application/json",
                    use_container_width=True,
                )


# ──────────────────── TAB 3: History ────────────────────────────────
with tab_history:
    st.subheader("🗂️ Screening History")
    if not st.session_state.history:
        st.info("No sessions yet — run a screening to see history here.")
    else:
        df_h = pd.DataFrame(st.session_state.history)
        df_h.index = range(1, len(df_h) + 1)
        st.dataframe(df_h, use_container_width=True)
        if st.button("🗑️ Clear history"):
            st.session_state.history = []
            st.rerun()

# ──────────────────── Footer ─────────────────────────────────────────
st.markdown("---")
st.caption(
    "CalibrHire by Anisca Jha"
)
