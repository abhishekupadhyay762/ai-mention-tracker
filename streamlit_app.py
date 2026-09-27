import os
import sys
import time
import json
import random
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime

# Guarantee project root is in sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Import DataForSeoClient and storage functions directly from app.py
from app import DataForSeoClient, init_db, create_run, save_result, save_competitor_metrics, get_run, get_results, get_competitor_metrics, get_history

# Initialize database
init_db()

# Streamlit Page Setup
st.set_page_config(
    page_title="AI Mention Tracker",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (SaaS Violet & Slate Theme)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    .stApp {
        background-color: #F8FAFC;
    }
    
    .metric-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 1rem;
        padding: 1.25rem;
        box-shadow: 0 4px 15px -3px rgba(15, 23, 42, 0.05);
    }
    
    .status-mentioned {
        background-color: #DCFCE7;
        color: #166534;
        font-weight: 700;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        border: 1px solid #BBF7D0;
    }
    
    .status-absent {
        background-color: #F1F5F9;
        color: #64748B;
        font-weight: 500;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
    }
    
    div[data-testid="stSidebarHeader"] {
        padding-bottom: 0rem;
    }
</style>
""", unsafe_allow_html=True)

# Main Header
st.markdown("""
<div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem;">
    <div style="width: 42px; height: 42px; background: linear-gradient(135deg, #7C3AED 0%, #3B82F6 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.5rem; font-weight: bold; box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);">
        🤖
    </div>
    <div>
        <h1 style="font-size: 1.8rem; font-weight: 800; color: #0F172A; margin: 0; line-height: 1.2;">AI Mention Tracker</h1>
        <p style="font-size: 0.85rem; color: #64748B; margin: 0; font-weight: 500;">Generative Search & Brand Share of Voice Intelligence</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Sidebar Setup & Config
st.sidebar.markdown("### ⚙️ Campaign Setup")

# Preset buttons
st.sidebar.markdown("**Quick Test Presets:**")
preset_col1, preset_col2 = st.sidebar.columns(2)
preset_type = None
if preset_col1.button("📚 Ebook Preset", use_container_width=True):
    preset_type = "ebook"
if preset_col2.button("🚀 Agency Preset", use_container_width=True):
    preset_type = "agency"

default_domain = "damcogroup.com" if preset_type == "ebook" else ("myagency.com" if preset_type == "agency" else "example.com")
default_brand = "Damco Solutions" if preset_type == "ebook" else ("Apex Marketing" if preset_type == "agency" else "Your Brand")
default_kw_high = "best ebook conversion companies\ntop ebook publishing services" if preset_type == "ebook" else ("best digital marketing agencies\ntop seo companies" if preset_type == "agency" else "digital marketing course")
default_kw_brand = "damco solutions reviews" if preset_type == "ebook" else ("apex marketing agency" if preset_type == "agency" else "your brand name")
default_comps = "suntecindia.com\npapertrue.com\nbookbaby.com" if preset_type == "ebook" else ("agencyone.com\nagencytwo.com" if preset_type == "agency" else "competitor1.com\ncompetitor2.com")

use_demo = st.sidebar.checkbox("⚡ Use Instant Demo Mode", value=True, help="Simulate AI responses without requiring a paid DataForSEO API key")

with st.sidebar.expander("🔑 DataForSEO API Key (Optional for Demo)", expanded=not use_demo):
    api_login = st.text_input("API Login", value="", placeholder="your-login@email.com")
    api_password = st.text_input("API Password", value="", type="password", placeholder="••••••••")

st.sidebar.markdown("---")
st.sidebar.markdown("**🏢 Brand Profile:**")
brand_name = st.sidebar.text_input("Brand Name", value=default_brand)
brand_domain = st.sidebar.text_input("Brand Domain", value=default_domain)

country = st.sidebar.selectbox("Target Country", ["United States", "United Kingdom", "India", "Canada", "Australia"])
language = st.sidebar.selectbox("Language", ["en", "es", "fr"])

st.sidebar.markdown("**⚔️ Competitor Domains:**")
competitors_raw = st.sidebar.text_area("Competitors (one per line)", value=default_comps, height=80)
competitors = [c.strip().lower() for c in competitors_raw.split("\n") if c.strip()]

st.sidebar.markdown("**🎯 Search Keywords:**")
keywords_high = st.sidebar.text_area("High-Volume Keywords", value=default_kw_high, height=70)
keywords_brand = st.sidebar.text_area("Brand & Niche Keywords", value=default_kw_brand, height=70)

keywords = [k.strip() for k in (keywords_high + "\n" + keywords_brand).split("\n") if k.strip()]

run_button = st.sidebar.button("🚀 Run AI Audit", type="primary", use_container_width=True)

# Application Logic
if run_button:
    if not brand_domain or not brand_name:
        st.error("Please enter your Brand Name and Brand Domain in the sidebar.")
    elif not keywords:
        st.error("Please enter at least one keyword to track.")
    elif not use_demo and (not api_login.strip() or not api_password.strip()):
        st.warning("To run Live tracking (Demo Mode unchecked), enter your DataForSEO API credentials. Or keep Demo Mode checked.")
    else:
        run_id = create_run(brand_domain, brand_name, country, language)
        st.session_state["last_run_id"] = run_id

        st.markdown("### ⏳ Tracking Execution")
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_box = st.empty()

        platforms = [
            ("google", "Google AI Mode"),
            ("chat_gpt", "ChatGPT"),
            ("perplexity", "Perplexity"),
            ("gemini", "Gemini"),
            ("claude", "Claude")
        ]

        total_steps = len(keywords) * len(platforms)
        current_step = 0
        logs = []

        client = None
        if not use_demo and api_login and api_password:
            client = DataForSeoClient(api_login, api_password)
        else:
            use_demo = True

        clean_brand_domain = brand_domain.lower()
        clean_brand_name = brand_name.lower()
        domain_mentions = {domain: 0 for domain in [clean_brand_domain] + competitors}

        for keyword in keywords:
            for platform_key, platform_name in platforms:
                current_step += 1
                progress = current_step / total_steps
                progress_bar.progress(progress)
                status_text.markdown(f"**Step {current_step}/{total_steps}:** Querying `{keyword}` on **{platform_name}**...")

                result = None
                if not use_demo and client:
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
                            result = {"text": f"⚠️ DataForSEO API Notice: {res.get('error') if res else 'No response'}", "sources": []}
                    except Exception as ex:
                        result = {"text": f"⚠️ Query Exception: {ex}", "sources": []}

                if use_demo or not result:
                    time.sleep(0.15)
                    is_brand_mentioned = random.choice([True, True, False])
                    comp_mentioned = [c for c in competitors if random.choice([True, False])]

                    text_parts = [f"Summary for '{keyword}' on {platform_name}:"]
                    sources = []

                    if is_brand_mentioned:
                        text_parts.append(f"Top recommendation includes {brand_name} ({clean_brand_domain}) for comprehensive {keyword} solutions.")
                        sources.append(f"https://{clean_brand_domain}/overview")
                    else:
                        text_parts.append(f"Leading platforms evaluated for {keyword}.")

                    for comp in comp_mentioned:
                        text_parts.append(f"Alternative: {comp.capitalize()} ({comp}).")
                        sources.append(f"https://{comp}/features")

                    result = {"text": "\n".join(text_parts), "sources": sources}

                text_lower = result["text"].lower()
                mentioned = clean_brand_domain in text_lower or clean_brand_name in text_lower

                if mentioned:
                    domain_mentions[clean_brand_domain] += 1

                competitor_mentions = []
                for comp in competitors:
                    if comp in text_lower:
                        competitor_mentions.append(comp)
                        domain_mentions[comp] += 1

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

                badge = "✅ Mentioned" if mentioned else "❌ Absent"
                logs.append(f"[{current_step}/{total_steps}] `{keyword}` ➔ {platform_name}: {badge}")
                log_box.code("\n".join(logs[-6:]))

        for domain, mentions in domain_mentions.items():
            sov = (mentions / total_steps) * 100 if total_steps > 0 else 0
            save_competitor_metrics(run_id, domain, mentions, None, round(sov, 1))

        status_text.success("🎉 Audit Complete!")
        time.sleep(0.5)
        st.rerun()

# Dashboard Results Display
run_id = st.session_state.get("last_run_id")

if run_id:
    run_data = get_run(run_id)
    results = get_results(run_id)
    metrics = get_competitor_metrics(run_id)

    if run_data and results:
        st.markdown("---")
        
        # Header Info
        header_col1, header_col2 = st.columns([3, 1])
        with header_col1:
            st.markdown(f"## 📊 Brand Intelligence Report: **{run_data['brand_name']}**")
            st.caption(f"Domain: `{run_data['brand_domain']}` • Country: `{run_data['country']}` • Run Date: `{run_data['run_date']}`")
            
        with header_col2:
            # CSV Download
            csv_rows = []
            for r in results:
                csv_rows.append({
                    "Keyword": r["keyword"],
                    "Platform": r["platform"],
                    "Mentioned": "Yes" if r["mentioned"] else "No",
                    "Sources Cited": r["sources_cited"],
                    "AI Text": (r["ai_response_text"] or "").replace("\n", " ")
                })
            df_csv = pd.DataFrame(csv_rows)
            st.download_button(
                label="📥 Export to CSV",
                data=df_csv.to_csv(index=False),
                file_name=f"AI_Mention_Audit_{run_data['brand_domain']}.csv",
                mime="text/csv",
                use_container_width=True
            )

        # Top Metric Cards
        total_queries = len(results)
        brand_mentions = sum(1 for r in results if r["mentioned"])
        visibility_score = round((brand_mentions / total_queries * 100), 1) if total_queries > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🏆 AI Visibility Score", f"{visibility_score} / 100")
        col2.metric("📊 Total AI Queries", total_queries)
        col3.metric("✅ Brand Mentions", brand_mentions)
        col4.metric("🎯 Tracked Keywords", len(set(r["keyword"] for r in results)))

        # Charts Section
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.markdown("### 📈 Share of Voice Benchmark (%)")
            if metrics:
                df_metrics = pd.DataFrame(metrics).sort_values(by="total_mentions", ascending=True)
                fig_sov = px.bar(
                    df_metrics,
                    x="share_of_voice",
                    y="domain",
                    orientation="h",
                    title="",
                    labels={"share_of_voice": "Share of Voice (%)", "domain": "Domain"},
                    text_auto=True,
                    color="domain",
                    color_discrete_map={run_data['brand_domain'].lower(): "#7C3AED"}
                )
                fig_sov.update_layout(showlegend=False, height=320, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_sov, use_container_width=True)

        with chart_col2:
            st.markdown("### 🍩 Platform Mentions Distribution")
            platform_counts = {}
            for r in results:
                if r["mentioned"]:
                    platform_counts[r["platform"].replace("_", " ").title()] = platform_counts.get(r["platform"].replace("_", " ").title(), 0) + 1
            
            if platform_counts:
                df_platforms = pd.DataFrame(list(platform_counts.items()), columns=["Platform", "Mentions"])
                fig_p = px.pie(
                    df_platforms,
                    names="Platform",
                    values="Mentions",
                    hole=0.4,
                    color_discrete_sequence=["#4285F4", "#10A37F", "#22B8CD", "#7C3AED", "#F59E0B"]
                )
                fig_p.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_p, use_container_width=True)

        # Actionable GEO Recommendations Banner
        st.markdown("""
        <div style="background: linear-gradient(135deg, #0F172A 0%, #1E1B4B 100%); color: white; padding: 1.25rem; border-radius: 1rem; margin-bottom: 1.5rem; border: 1px solid rgba(124, 58, 237, 0.3);">
            <h4 style="margin: 0 0 0.75rem 0; color: #EDE9FE; font-weight: 800; font-size: 1rem;">💡 Actionable GEO (Generative Engine Optimization) Tips</h4>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; font-size: 0.8rem;">
                <div style="background: rgba(255,255,255,0.08); padding: 0.75rem; border-radius: 0.75rem;">
                    <strong style="color: #A78BFA;">1. Review Citations</strong><br>
                    Ensure your domain is featured on high-authority directories & review sites cited by AI models.
                </div>
                <div style="background: rgba(255,255,255,0.08); padding: 0.75rem; border-radius: 0.75rem;">
                    <strong style="color: #A78BFA;">2. Target Comparison Terms</strong><br>
                    Publish comparison articles & case studies for queries like "best solutions for [keyword]".
                </div>
                <div style="background: rgba(255,255,255,0.08); padding: 0.75rem; border-radius: 0.75rem;">
                    <strong style="color: #A78BFA;">3. Schema Entity Data</strong><br>
                    Add Schema.org Organization metadata so LLMs easily recognize your brand name & domain.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Keyword Mention Matrix Table
        st.markdown("### 🗺️ Keyword Mention Matrix")
        df_results = pd.DataFrame(results)
        if not df_results.empty:
            df_results["Status"] = df_results["mentioned"].apply(lambda x: "✅ Mentioned" if x else "❌ Absent")
            df_results["Platform"] = df_results["platform"].str.replace("_", " ").str.title()
            pivot_df = df_results.pivot(index="keyword", columns="Platform", values="Status").fillna("N/A")
            st.dataframe(pivot_df, use_container_width=True)

        # AI Responses & Source Citations Detail Accordion
        st.markdown("### 🔍 Detailed AI Responses & Sources")
        unique_kws = list(set(r["keyword"] for r in results))
        selected_kw = st.selectbox("Filter by Keyword Query", unique_kws)

        kw_results = [r for r in results if r["keyword"] == selected_kw]
        for r in kw_results:
            badge = "✅ Brand Mentioned" if r["mentioned"] else "❌ Absent"
            with st.expander(f"🤖 {r['platform'].replace('_', ' ').title()} — {badge}"):
                text_content = r["ai_response_text"] or ""
                st.markdown(text_content)
                if r["sources_cited"]:
                    try:
                        sources = json.loads(r["sources_cited"]) if isinstance(r["sources_cited"], str) else r["sources_cited"]
                        if sources:
                            st.markdown("**Cited Sources:**")
                            for s in sources:
                                st.markdown(f"- [{s}]({s})")
                    except Exception:
                        pass
else:
    st.info("👈 Set your Brand Profile & Search Keywords in the sidebar and click **Run AI Audit** to generate your intelligence dashboard!")
