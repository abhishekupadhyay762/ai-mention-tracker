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

# Explicitly bind template folder path
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

# Custom Styling to match the original purple brand theme
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stHeader"] {display: none;}
    [data-testid="stSidebar"] {display: none;}
    
    .main .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        max-width: 1000px !important;
    }
    
    /* Card Container */
    div[data-testid="stForm"] {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 1.25rem !important;
        padding: 2rem !important;
        box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.08) !important;
    }
    
    /* Inputs Styling */
    .stTextInput input, .stTextArea textarea, .stSelectbox select {
        border-radius: 0.75rem !important;
        border: 1px solid #cbd5e1 !important;
        font-size: 0.95rem !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #7C3AED !important;
        box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.2) !important;
    }
    
    /* Submit Button (Purple Gradient) */
    div[data-testid="stFormSubmitButton"] button {
        background: linear-gradient(135deg, #7C3AED 0%, #6D28D9 100%) !important;
        color: white !important;
        border: none !important;
        padding: 0.85rem 2rem !important;
        font-weight: 800 !important;
        font-size: 1.05rem !important;
        border-radius: 0.85rem !important;
        width: 100% !important;
        box-shadow: 0 4px 15px rgba(124, 58, 237, 0.35) !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stFormSubmitButton"] button:hover {
        background: linear-gradient(135deg, #6D28D9 0%, #5B21B6 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(124, 58, 237, 0.45) !important;
    }
    
    iframe {
        width: 100% !important;
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)

if "current_run_id" not in st.session_state:
    st.session_state["current_run_id"] = None


# ───────────────────────── DASHBOARD VIEW ─────────────────────────
if st.session_state["current_run_id"]:
    run_id = st.session_state["current_run_id"]
    
    col1, col2 = st.columns([10, 1])
    with col2:
        st.write("")
        if st.button("🔄 New Run"):
            st.session_state["current_run_id"] = None
            st.rerun()

    with flask_app.test_request_context():
        run_data = get_run(run_id)
        if not run_data:
            st.session_state["current_run_id"] = None
            st.rerun()

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
            run=run_data, results=results, metrics=metrics,
            heatmap=heatmap, platforms=platforms, keywords=keywords,
            platform_counts=platform_counts, platform_breakdown=platform_counts,
            history=history, trend_labels=trend_labels, trend_datasets=trend_datasets, json=json
        )

        dash_height = max(1600, 700 + len(keywords) * 120 + len(results) * 55)
        components.html(rendered_html, height=dash_height, scrolling=True)


# ───────────────────────── SETUP FORM VIEW ─────────────────────────
else:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:6px;">
        <div style="width:48px;height:48px;border-radius:14px;background:linear-gradient(135deg,#7C3AED,#3B82F6);display:flex;align-items:center;justify-content:center;font-size:24px;color:white;box-shadow:0 4px 15px rgba(124,58,237,0.35);">🤖</div>
        <div>
            <h1 style="margin:0;font-size:28px;font-weight:800;color:#0F172A;letter-spacing:-0.5px;">AI Mention Tracker</h1>
            <p style="margin:0;font-size:12px;color:#8B5CF6;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;">GEO Intelligence Engine</p>
        </div>
    </div>
    <p style="color:#64748B;font-size:14px;margin-bottom:20px;">Analyze your brand presence, share of voice, and citations across Google AI, ChatGPT, Perplexity, Gemini & Claude.</p>
    """, unsafe_allow_html=True)

    with st.form("setup_form", clear_on_submit=False):
        # 1. API Credentials
        st.markdown("#### 🔑 1. DataForSEO Credentials")
        col1, col2 = st.columns(2)
        with col1:
            api_login = st.text_input("DataForSEO API Login (Optional)", placeholder="your-email@example.com", key="api_login")
        with col2:
            api_password = st.text_input("DataForSEO API Password (Optional)", type="password", placeholder="••••••••", key="api_password")
        
        use_demo = st.checkbox("⚡ Use Instant Demo Mode (Simulates realistic AI responses without API credits)", value=True, key="use_demo")
        st.caption("Uncheck Demo Mode to query live production models with your DataForSEO credentials.")
        st.markdown("<hr style='margin: 1.2rem 0; border: none; border-top: 1px solid #f1f5f9;'>", unsafe_allow_html=True)

        # 2. Target Brand Profile
        st.markdown("#### 🏢 2. Target Brand Profile")
        col1, col2 = st.columns(2)
        with col1:
            brand_domain = st.text_input("Brand Domain", value="damcogroup.com", placeholder="example.com", key="brand_domain")
            country = st.selectbox("Target Market Country", [
                "United States", "United Kingdom", "India", "Canada", "Australia", "Germany", "France"
            ], index=0, key="country")
        with col2:
            brand_name = st.text_input("Brand Name", value="Damco Solutions", placeholder="Your Brand Name", key="brand_name")
            language = st.selectbox("Language", [
                ("en", "English (en)"), ("es", "Spanish (es)"), ("fr", "French (fr)"), ("de", "German (de)")
            ], format_func=lambda x: x[1], index=0, key="language")
        st.markdown("<hr style='margin: 1.2rem 0; border: none; border-top: 1px solid #f1f5f9;'>", unsafe_allow_html=True)

        # 3. Competitor Intelligence
        st.markdown("#### ⚔️ 3. Competitor Domains Benchmark")
        st.caption("Enter competitor domains to benchmark against. Leave unused fields blank.")
        c1, c2, c3 = st.columns(3)
        with c1:
            comp1 = st.text_input("Competitor 1", value="suntecindia.com", placeholder="competitor1.com", key="comp1")
            comp4 = st.text_input("Competitor 4", placeholder="competitor4.com", key="comp4")
        with c2:
            comp2 = st.text_input("Competitor 2", value="papertrue.com", placeholder="competitor2.com", key="comp2")
            comp5 = st.text_input("Competitor 5", placeholder="competitor5.com", key="comp5")
        with c3:
            comp3 = st.text_input("Competitor 3", value="bookbaby.com", placeholder="competitor3.com", key="comp3")
        st.markdown("<hr style='margin: 1.2rem 0; border: none; border-top: 1px solid #f1f5f9;'>", unsafe_allow_html=True)

        # 4. Keywords Strategy
        st.markdown("#### 🔍 4. GEO Search Queries Strategy")
        k_col1, k_col2 = st.columns(2)
        with k_col1:
            keywords_high = st.text_area(
                "High-Volume Search Queries (one per line)",
                value="best ebook conversion companies\ntop ebook publishing services",
                height=110,
                key="keywords_high"
            )
        with k_col2:
            keywords_brand = st.text_area(
                "Brand & Niche Queries (one per line)",
                value="damco solutions reviews",
                height=110,
                key="keywords_brand"
            )

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        submitted = st.form_submit_button("🚀 Run GeoPulse AI Mention Audit", use_container_width=True)

    if submitted:
        bd = (brand_domain or "").strip()
        bn = (brand_name or "").strip()
        if not bd or not bn:
            st.error("Please provide both Brand Domain and Brand Name.")
            st.stop()

        kw_high = [k.strip() for k in (keywords_high or "").split("\n") if k.strip()]
        kw_brand = [k.strip() for k in (keywords_brand or "").split("\n") if k.strip()]
        all_keywords = kw_high + kw_brand
        if not all_keywords:
            st.error("Please enter at least one keyword query.")
            st.stop()

        raw_competitors = [comp1, comp2, comp3, comp4, comp5]
        competitors = [c.strip().lower() for c in raw_competitors if c and c.strip()]

        lang_code = language[0] if isinstance(language, tuple) else "en"
        is_demo = use_demo or not api_login or not api_password

        # ── EXECUTE AUDIT ──
        run_id = create_run(bd, bn, country, lang_code)

        client = None
        if not is_demo:
            client = DataForSeoClient(api_login, api_password)

        clean_brand_domain = bd.lower()
        clean_brand_name = bn.lower()
        domain_mentions = {d: 0 for d in [clean_brand_domain] + competitors}

        platforms = [
            ("google", "Google AI Mode"),
            ("chat_gpt", "ChatGPT"),
            ("perplexity", "Perplexity"),
            ("gemini", "Gemini"),
            ("claude", "Claude")
        ]

        total_steps = len(all_keywords) * len(platforms)
        current_step = 0

        st.markdown(f"### ⚡ Running Live Audit for **{bn}**...")
        progress_bar = st.progress(0, text="Initializing GEO Audit Engine...")
        status_box = st.empty()

        for keyword in all_keywords:
            for platform_key, platform_name in platforms:
                current_step += 1
                pct = current_step / total_steps
                progress_bar.progress(pct, text=f"[{current_step}/{total_steps}] Checking \"{keyword}\" on {platform_name}...")

                result = None
                if not is_demo and client:
                    try:
                        if platform_key == "google":
                            res = client.check_google_ai_mode(keyword, country, lang_code)
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
                    time.sleep(0.06)
                    is_brand_mentioned = random.choice([True, True, False])
                    comp_mentioned = [c for c in competitors if random.choice([True, False])]
                    result = _generate_demo_response(
                        keyword, platform_name,
                        bn, bd,
                        competitors, comp_mentioned,
                        is_brand_mentioned
                    )

                text_lower = result["text"].lower()
                mentioned = clean_brand_domain in text_lower or clean_brand_name in text_lower

                if mentioned:
                    domain_mentions[clean_brand_domain] += 1

                competitor_mentions = []
                for comp in competitors:
                    if comp in text_lower:
                        competitor_mentions.append(comp)
                        domain_mentions[comp] += 1

                discovered_domains = extract_domains_from_text(result["text"])
                for dom in discovered_domains:
                    if dom != clean_brand_domain and dom not in competitor_mentions and dom not in competitors:
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

                icon = "✅ Mentioned" if mentioned else "❌ Not Featured"
                status_box.markdown(f"`[{current_step}/{total_steps}]` **{keyword}** ({platform_name}) → **{icon}**")

        for domain, mentions in domain_mentions.items():
            sov = (mentions / total_steps) * 100 if total_steps > 0 else 0
            save_competitor_metrics(run_id, domain, mentions, None, round(sov, 1))

        progress_bar.progress(1.0, text="✅ Audit complete! Generating executive dashboard...")
        time.sleep(0.5)

        st.session_state["current_run_id"] = run_id
        st.rerun()
