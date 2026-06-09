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
from src.scorer import ScoringWeights, ResumeScorer
from src.screener import ResumeScreener
from src.utils import format_duration, estimate_tokens

st.set_page_config(page_title="CalibrHire", page_icon="🎯", layout="wide")

# ─────────────────────────── Enhanced CSS ─────────────────────────────
st.markdown("""
<style>
    .stApp { background: #f8fafc; }
    .header-card { 
        background: linear-gradient(135deg, #1e293b, #334155); 
        padding: 2rem; border-radius: 12px; color: white; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.1); margin-bottom: 2rem;
    }
    .metric-card { 
        background: white; border-radius: 10px; padding: 1.2rem; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-left: 4px solid #3b82f6;
    }
    .gemini-badge {
        background: #eff6ff; color: #1e40af; padding: 4px 10px; 
        border-radius: 6px; font-size: 0.8rem; font-weight: 600; border: 1px solid #bfdbfe;
    }
    .stButton>button { width: 100%; border-radius: 6px; font-weight: 600; }
    div.stExpander { border-radius: 8px; border: 1px solid #e2e8f0; }
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
    st.header("⚙️ Engine Config")
    provider = st.selectbox("AI Provider", ["Google Gemini (FREE ✅)", "Anthropic (Claude)", "OpenAI (GPT)"])
    
    prov_key = "gemini" if "Gemini" in provider else "api"
    if prov_key == "gemini":
        st.markdown('<div class="gemini-badge">Free Tier — No billing needed</div>', unsafe_allow_html=True)

    api_key = st.text_input("API Key", type="password")
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
    pass

# ──────────────────── TAB 2: Results ────────────────────────────────
with tab_results:
    if "session_results" not in st.session_state or st.session_state.session_results is None:
        st.info("🚀 Run a screening session to see analytics.")
    else:
        ranked = st.session_state.session_results.ranked
        
        # 1. METRIC BOXES AT TOP
        # Initialize an empty dictionary
        stats = {}
        
        for r in ranked:
            cat = r.recommendation.replace("Strong Yes", "Strong")
            # If the category isn't in the dictionary, it starts at 0, then adds 1
            stats[cat] = stats.get(cat, 0) + 1
            
        colors = {"Strong": "#10b981", "Yes": "#005ecb", "Maybe": "#d97706", "No": "#ef4444"}
        
        # Only iterate over the categories that actually exist in your data
        cols = st.columns(len(stats) if len(stats) > 0 else 1)
        if len(stats) > 0:
            for col, (label, count) in zip(cols, stats.items()):
                col.markdown(f"""
                <div style="background-color: {colors.get(label, '#94a3b8')}; padding: 10px; border-radius: 5px; color: white; text-align: center; font-weight: bold;">
                    {label}<br><span style="font-size: 1.2rem;">{count}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No data available to display metrics.")

        # 2. GRAPH: Origin-to-value lines + Forced 4-item Legend
        # 2. GRAPH: Origin-to-value lines (Horizontal) + Forced 4-item Legend
        if ranked:
            fig = go.Figure()
            
            # Draw horizontal lines from origin (0, score) to each data point (i, score)
            for i, r in enumerate(ranked):
                fig.add_trace(go.Scatter(
                    x=[0, i], y=[r.overall_score, r.overall_score],
                    mode='lines', line=dict(color='black', width=1),
                    showlegend=False, hoverinfo='skip'
                ))
            
            # Add points, ensuring all 4 categories are forced into the legend
            for cat, color in colors.items():
                cat_indices = [i for i, r in enumerate(ranked) if r.recommendation.replace("Strong Yes", "Strong") == cat]
                has_data = len(cat_indices) > 0
                fig.add_trace(go.Scatter(
                    x=[i for i in cat_indices] if has_data else [None],
                    y=[ranked[i].overall_score for i in cat_indices] if has_data else [None],
                    mode='markers', name=cat,
                    marker=dict(color=color, size=12),
                    showlegend=True
                ))
            
            fig.update_layout(
                plot_bgcolor="white",
                xaxis=dict(showgrid=False, zeroline=True, linecolor='gray', showticklabels=False),
                yaxis=dict(range=[0, 105], showgrid=False, zeroline=True, linecolor='gray'),
                legend=dict(
                    orientation="v", x=1.00, y=1.00, 
                    xanchor="right", yanchor="top",
                    bordercolor="gray", borderwidth=1,
                    traceorder="normal"
                ),
                margin=dict(l=40, r=120, t=20, b=40)
            )
            
            st.plotly_chart(fig, use_container_width=True)

        # 3. EXPORT
        st.divider()
        c1, c2 = st.columns(2)
        c1.download_button("⬇️ Export CSV", data=pd.DataFrame([r.to_dict() for r in ranked]).to_csv(), file_name="results.csv", use_container_width=True)
        c2.download_button("⬇️ Export JSON", data=json.dumps([r.to_dict() for r in ranked]), file_name="results.json", use_container_width=True)

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
    pass
