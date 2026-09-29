import os
import sys
import time
import json
import random
import streamlit as st
import streamlit.components.v1 as components

# Guarantee root directory is in sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from flask import render_template
from app import (
    app as flask_app, init_db, create_run, save_result,
    save_competitor_metrics, get_run, get_results,
    get_competitor_metrics, get_history, DataForSeoClient,
    _generate_demo_response, extract_domains_from_text
)

# Explicitly bind template folder path for Jinja2 on Streamlit Cloud (Linux)
template_dir = os.path.join(root_dir, "templates")
flask_app.template_folder = template_dir

# Initialize database
init_db()

# Streamlit Page Setup
st.set_page_config(
    page_title="AI Mention Tracker — GEO Intelligence",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stHeader"] {display: none;}
    [data-testid="stSidebar"] {display: none;}
    .block-container {
        padding-top: 1rem !important;
        max-width: 100% !important;
    }
    iframe {
        width: 100% !important;
        border: none !important;
    }
    /* Style the form area */
    .stForm {
        border: 1px solid #e2e8f0 !important;
        border-radius: 1rem !important;
        padding: 1.5rem !important;
    }
    div[data-testid="stVerticalBlock"] > div:has(> div.stButton) button {
        background: linear-gradient(135deg, #7C3AED 0%, #6D28D9 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        font-weight: 700;
        font-size: 1rem;
        border-radius: 0.75rem;
        width: 100%;
    }
    div[data-testid="stVerticalBlock"] > div:has(> div.stButton) button:hover {
        background: linear-gradient(135deg, #6D28D9 0%, #5B21B6 100%);
    }
</style>
""", unsafe_allow_html=True)

# ───────────────────────── SESSION STATE HELPERS ─────────────────────────
if "current_run_id" not in st.session_state:
    st.session_state["current_run_id"] = None
if "num_competitors" not in st.session_state:
    st.session_state["num_competitors"] = 3
if "running" not in st.session_state:
    st.session_state["running"] = False


def add_competitor():
    st.session_state["num_competitors"] += 1


# ───────────────────────── VIEW: SETUP FORM ─────────────────────────
def show_setup_form():
    # Header
    st.markdown("""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
        <div style="width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,#7C3AED,#3B82F6);display:flex;align-items:center;justify-content:center;font-size:24px;color:white;box-shadow:0 4px 15px rgba(124,58,237,0.3);">🤖</div>
        <div>
            <h1 style="margin:0;font-size:28px;font-weight:800;color:#0F172A;">AI Mention Tracker</h1>
            <p style="margin:0;font-size:12px;color:#8B5CF6;font-weight:600;letter-spacing:1px;">GEO INTELLIGENCE ENGINE</p>
        </div>
    </div>
    <p style="color:#64748B;font-size:14px;margin-bottom:24px;">Track how your brand is mentioned across ChatGPT, Google AI Mode, Perplexity, Gemini & Claude.</p>
    """, unsafe_allow_html=True)

    with st.form("setup_form", clear_on_submit=False):
        # ── Section: DataForSEO Credentials ──
        st.markdown("##### 🔑 DataForSEO Credentials")
        col1, col2 = st.columns(2)
        with col1:
            api_login = st.text_input("API Login", placeholder="your-dataforseo-login@email.com", key="api_login")
        with col2:
            api_password = st.text_input("API Password", type="password", placeholder="••••••••", key="api_password")

        use_demo = st.checkbox("✨ Demo Mode (instant simulation — no API charges)", value=True, key="use_demo")
        st.caption("Get your API key at [dataforseo.com](https://dataforseo.com)")
        st.divider()

        # ── Section: Brand Info ──
        st.markdown("##### 🏢 Your Brand")
        col1, col2 = st.columns(2)
        with col1:
            brand_domain = st.text_input("Brand Domain", placeholder="example.com", key="brand_domain")
            country = st.selectbox("Target Country", [
                "United States", "United Kingdom", "Canada", "Australia",
                "India", "Germany", "France", "Spain", "Brazil", "Japan"
            ], index=4, key="country")
        with col2:
            brand_name = st.text_input("Brand Name", placeholder="Your Brand", key="brand_name")
            language = st.selectbox("Language", [
                ("en", "English"), ("fr", "French"), ("es", "Spanish"),
                ("de", "German"), ("pt", "Portuguese"), ("ja", "Japanese")
            ], format_func=lambda x: x[1], index=0, key="language")
        st.divider()

        # ── Section: Competitors ──
        st.markdown("##### ⚔️ Competitor Domains")
        st.caption("Enter up to 5 competitor domains. Leave blank to skip.")
        competitor_values = []
        cols = st.columns(5)
        for i in range(5):
            with cols[i]:
                val = st.text_input(
                    f"Competitor {i+1}",
                    placeholder="competitor.com",
                    key=f"comp_{i}",
                )
                competitor_values.append(val)
        st.divider()

        # ── Section: Keywords ──
        st.markdown("##### 🔍 Keywords to Track")
        col1, col2 = st.columns(2)
        with col1:
            keywords_high = st.text_area(
                "High-Volume Keywords",
                placeholder="best ebook conversion companies\ndigital marketing agency",
                height=120,
                key="keywords_high"
            )
        with col2:
            keywords_brand = st.text_area(
                "Brand / Niche Keywords",
                placeholder="your brand name reviews\nyour brand pricing",
                height=120,
                key="keywords_brand"
            )
        st.caption("Enter one keyword per line.")

        # ── Submit ──
        submitted = st.form_submit_button(
            "🚀 Run GEO Pulse — AI Mention Audit",
            use_container_width=True
        )

    if submitted:
        # Validate
        bd = (brand_domain or "").strip()
        bn = (brand_name or "").strip()
        if not bd or not bn:
            st.error("Please enter your Brand Domain and Brand Name.")
            return

        kw_high = [k.strip() for k in (keywords_high or "").split("\n") if k.strip()]
        kw_brand = [k.strip() for k in (keywords_brand or "").split("\n") if k.strip()]
        all_keywords = kw_high + kw_brand
        if not all_keywords:
            st.error("Please enter at least one keyword.")
            return

        lang_code = language[0] if isinstance(language, tuple) else "en"
        competitors = [c.strip() for c in competitor_values if c.strip()]

        is_demo = use_demo or not api_login or not api_password

        # Run the audit
        run_audit(
            api_login=api_login or "",
            api_password=api_password or "",
            brand_domain=bd,
            brand_name=bn,
            country=country,
            language=lang_code,
            competitors=competitors,
            keywords=all_keywords,
            is_demo=is_demo
        )


# ───────────────────────── EXECUTE AUDIT ─────────────────────────
def run_audit(api_login, api_password, brand_domain, brand_name, country, language, competitors, keywords, is_demo):
    run_id = create_run(brand_domain, brand_name, country, language)

    client = None
    if not is_demo:
        client = DataForSeoClient(api_login, api_password)

    clean_brand_domain = brand_domain.lower()
    clean_brand_name = brand_name.lower()
    clean_competitors = [c.lower() for c in competitors if c.strip()]
    domain_mentions = {d: 0 for d in [clean_brand_domain] + clean_competitors}

    platforms = [
        ("google", "Google AI Mode"),
        ("chat_gpt", "ChatGPT"),
        ("perplexity", "Perplexity"),
        ("gemini", "Gemini"),
        ("claude", "Claude")
    ]

    total_steps = len(keywords) * len(platforms)
    current_step = 0

    progress_bar = st.progress(0, text="Starting AI Mention Audit...")
    status_container = st.empty()

    for keyword in keywords:
        for platform_key, platform_name in platforms:
            current_step += 1
            pct = current_step / total_steps
            progress_bar.progress(pct, text=f"[{current_step}/{total_steps}] \"{keyword}\" → {platform_name}...")

            result = None
            if not is_demo and client:
                try:
                    if platform_key == "google":
                        res = client.check_google_ai_mode(keyword, country, language)
                    elif platform_key == "chat_gpt":
                        res = client.check_chatgpt(keyword)
                    elif platform_key == "perplexity":
                        res = client.check_perplexity(keyword)
                    elif platform_key == "gemini":
                        res = client.check_gemini(keyword)
                    elif platform_key == "claude":
                        res = client.check_claude(keyword)

                    if res and not res.get("error"):
                        result = {"text": res.get("text", ""), "sources": res.get("sources", [])}
                    else:
                        err_msg = res.get("error") if res else "No response"
                        result = {"text": f"⚠️ DataForSEO API Notice: {err_msg}", "sources": []}
                except Exception as ex:
                    result = {"text": f"⚠️ Query Exception: {ex}", "sources": []}

            if is_demo or not result:
                time.sleep(0.1)
                is_brand_mentioned = random.choice([True, True, False])
                comp_mentioned = [c for c in clean_competitors if random.choice([True, False])]
                result = _generate_demo_response(
                    keyword, platform_name,
                    brand_name, brand_domain,
                    clean_competitors, comp_mentioned,
                    is_brand_mentioned
                )

            text_lower = result["text"].lower()
            mentioned = clean_brand_domain in text_lower or clean_brand_name in text_lower

            if mentioned:
                domain_mentions[clean_brand_domain] += 1

            competitor_mentions = []
            for comp in clean_competitors:
                if comp in text_lower:
                    competitor_mentions.append(comp)
                    domain_mentions[comp] += 1

            # Discover additional domains
            discovered_domains = extract_domains_from_text(result["text"])
            for dom in discovered_domains:
                if dom != clean_brand_domain and dom not in competitor_mentions and dom not in clean_competitors:
                    competitor_mentions.append(dom)
                    if dom not in domain_mentions:
                        domain_mentions[dom] = 0
                    domain_mentions[dom] += 1

            save_result(
                run_id=run_id,
                keyword=keyword,
                platform=platform_key,
                mentioned=mentioned,
                mention_position=1 if mentioned else None,
                sources_cited=result["sources"],
                competitor_mentions=competitor_mentions,
                ai_response_text=result["text"]
            )

            # Show live status
            icon = "✅" if mentioned else "❌"
            status_container.markdown(f"`[{current_step}/{total_steps}]` **{keyword}** → {platform_name} {icon}")

    # Save competitor metrics
    for domain, mentions in domain_mentions.items():
        sov = (mentions / total_steps) * 100 if total_steps > 0 else 0
        save_competitor_metrics(run_id, domain, mentions, None, round(sov, 1))

    progress_bar.progress(1.0, text="✅ Audit complete! Loading dashboard...")
    time.sleep(0.5)

    st.session_state["current_run_id"] = run_id
    st.rerun()


# ───────────────────────── VIEW: DASHBOARD ─────────────────────────
def show_dashboard(run_id):
    run_data = get_run(run_id)
    if not run_data:
        st.error("Run not found.")
        st.session_state["current_run_id"] = None
        return

    results = get_results(run_id)
    metrics = get_competitor_metrics(run_id)

    keywords = list(dict.fromkeys([r["keyword"] for r in results]))
    platforms = ["google", "chat_gpt", "perplexity", "gemini", "claude"]

    heatmap = {k: {p: None for p in platforms} for k in keywords}
    for r in results:
        heatmap[r["keyword"]][r["platform"]] = {
            "mentioned": r["mentioned"],
            "position": r["mention_position"],
            "text": r["ai_response_text"],
            "sources": json.loads(r["sources_cited"]) if r["sources_cited"] else []
        }

    platform_counts = {p: 0 for p in platforms}
    for r in results:
        if r["mentioned"]:
            platform_counts[r["platform"]] += 1

    history = get_history(run_data["brand_domain"])

    # "New Run" button
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("🔄 New Run"):
            st.session_state["current_run_id"] = None
            st.rerun()

    # Render the Flask/Jinja2 dashboard template inside a component
    with flask_app.test_request_context():
        trend_labels = []
        trend_datasets = {}
        for h in history:
            rd = h['run']['run_date']
            trend_labels.append(rd[:10] if isinstance(rd, str) else rd.strftime('%Y-%m-%d'))
        for m in metrics:
            domain = m['domain']
            trend_datasets[domain] = []
            for h in history:
                val = next((item['total_mentions'] for item in h['metrics'] if item['domain'] == domain), 0)
                trend_datasets[domain].append(val)

        rendered_html = render_template(
            "dashboard.html",
            run=run_data,
            results=results,
            metrics=metrics,
            heatmap=heatmap,
            platforms=platforms,
            keywords=keywords,
            platform_counts=platform_counts,
            platform_breakdown=platform_counts,
            history=history,
            trend_labels=trend_labels,
            trend_datasets=trend_datasets,
            json=json
        )

    # Render dashboard — increase height for large keyword sets
    dash_height = max(1400, 600 + len(keywords) * 120 + len(results) * 50)
    components.html(rendered_html, height=dash_height, scrolling=True)


# ───────────────────────── MAIN ROUTER ─────────────────────────
run_id = st.session_state.get("current_run_id")
if run_id:
    show_dashboard(run_id)
else:
    show_setup_form()
