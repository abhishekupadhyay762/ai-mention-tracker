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
    app as flask_app, init_db, create_run, save_result, save_competitor_metrics,
    get_run, get_results, get_competitor_metrics, get_history, DataForSeoClient,
    extract_urls_from_text, extract_domains_from_text
)

# Explicitly bind template folder path for Jinja2 on Streamlit Cloud
template_dir = os.path.join(root_dir, "templates")
flask_app.template_folder = template_dir

# Initialize database
init_db()

# Streamlit Page Setup - Full Screen, Collapsed Sidebar
st.set_page_config(
    page_title="AI Mention Tracker",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Handle Reset / New Audit action
query_params = st.query_params
if "run_action" in query_params and query_params["run_action"] == "reset":
    if "current_run_id" in st.session_state:
        del st.session_state["current_run_id"]
    st.query_params.clear()
    st.rerun()

current_run_id = st.session_state.get("current_run_id")

if current_run_id:
    # -------------------------------------------------------------
    # DASHBOARD VIEW: 100% Full-Width, Seamless Layout, No Clipping
    # -------------------------------------------------------------
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        
        #MainMenu, footer, header, [data-testid="stHeader"], [data-testid="stSidebar"] {
            display: none !important;
        }
        .block-container {
            padding: 0rem !important;
            margin: 0rem !important;
            max-width: 100% !important;
            width: 100% !important;
        }
        iframe {
            width: 100% !important;
            height: 100vh !important;
            min-height: 1400px !important;
            border: none !important;
            display: block !important;
        }
    </style>
    """, unsafe_allow_html=True)

    with flask_app.test_request_context():
        run_data = get_run(current_run_id)
        results = get_results(current_run_id)
        metrics = get_competitor_metrics(current_run_id)
        
        keywords = list(set([r["keyword"] for r in results]))
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
        
        rendered_html = render_template(
            "dashboard.html",
            run=run_data,
            results=results,
            metrics=metrics,
            heatmap=heatmap,
            platforms=platforms,
            keywords=keywords,
            platform_counts=platform_counts,
            history=history,
            json=json
        )

        # Inject Reset link listener into Dashboard HTML for smooth reset
        reset_bridge = """
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            const auditLinks = document.querySelectorAll('a[href="/"]');
            auditLinks.forEach(link => {
                link.onclick = function(e) {
                    e.preventDefault();
                    window.parent.location.search = '?run_action=reset';
                };
            });
        });
        </script>
        """
        full_dashboard = rendered_html.replace("</body>", reset_bridge + "</body>")
        components.html(full_dashboard, height=1600, scrolling=True)

else:
    # -------------------------------------------------------------
    # SETUP FORM VIEW: Centered Elegant Card Container
    # -------------------------------------------------------------
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', sans-serif;
            background-color: #F8FAFC !important;
        }
        #MainMenu, footer, header, [data-testid="stHeader"], [data-testid="stSidebar"] {
            display: none !important;
        }
        .block-container {
            padding: 2.5rem 1.5rem !important;
            max-width: 860px !important;
            margin: 0 auto !important;
        }
        .main-header {
            margin-bottom: 1.5rem;
        }
        .badge-step {
            background: #EDE9FE;
            color: #6D28D9;
            font-weight: 700;
            font-size: 11px;
            padding: 4px 12px;
            border-radius: 9999px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            display: inline-block;
            margin-bottom: 8px;
        }
        .section-title {
            font-size: 15px;
            font-weight: 800;
            color: #0F172A;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .step-num {
            background: #EDE9FE;
            color: #7C3AED;
            width: 24px;
            height: 24px;
            border-radius: 6px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 900;
        }
        div[data-testid="stForm"] {
            border: 1px solid #E2E8F0 !important;
            border-radius: 20px !important;
            padding: 28px !important;
            background: #FFFFFF !important;
            box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.06) !important;
        }
        div[data-testid="stFormSubmitButton"] > button {
            background: linear-gradient(135deg, #7C3AED 0%, #6D28D9 100%) !important;
            color: white !important;
            font-weight: 800 !important;
            font-size: 15px !important;
            padding: 14px 28px !important;
            border-radius: 14px !important;
            border: none !important;
            width: 100% !important;
            box-shadow: 0 10px 20px -3px rgba(124, 58, 237, 0.3) !important;
            transition: all 0.2s ease !important;
        }
        div[data-testid="stFormSubmitButton"] > button:hover {
            background: linear-gradient(135deg, #6D28D9 0%, #5B21B6 100%) !important;
            transform: translateY(-1px) !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Header
    st.markdown("""
    <div class="main-header">
        <span class="badge-step">Campaign Setup • Step 1 of 2</span>
        <h2 style="font-size: 30px; font-weight: 900; color: #0F172A; margin: 4px 0; letter-spacing: -0.02em;">Setup AI Mention Tracker Audit</h2>
        <p style="color: #64748B; font-size: 14px; margin: 0;">Analyze your brand visibility, share of voice, and cited sources across Google AI, ChatGPT, Perplexity, Gemini & Claude.</p>
    </div>
    """, unsafe_allow_html=True)

    # Quick Preset Buttons
    pcol1, pcol2 = st.columns(2)
    with pcol1:
        if st.button("📚 Load Ebook Services Preset", use_container_width=True):
            st.session_state["f_domain"] = "damcogroup.com"
            st.session_state["f_name"] = "Damco Solutions"
            st.session_state["f_comps"] = "suntecindia.com"
            st.session_state["f_keywords"] = "top ebook conversion companies for enterprise\ntop data cleansing companies"
            st.rerun()
    with pcol2:
        if st.button("🚀 Load Marketing Agency Preset", use_container_width=True):
            st.session_state["f_domain"] = "webfx.com"
            st.session_state["f_name"] = "WebFX"
            st.session_state["f_comps"] = "ignitevisibility.com\nsmartites.com\ndisruptiveadvertising.com"
            st.session_state["f_keywords"] = "best digital marketing agency for enterprise\ntop seo companies"
            st.rerun()

    # Main Setup Form
    with st.form("setup_tracker_form"):
        # Section 1: API Configuration
        st.markdown('<div class="section-title"><span class="step-num">1</span> Multi-Model Data API</div>', unsafe_allow_html=True)
        col_api1, col_api2 = st.columns(2)
        with col_api1:
            api_login = st.text_input("DataForSEO API Login (Email)", value=st.session_state.get("f_login", "seo@rockettech.in"), placeholder="your-login@email.com")
        with col_api2:
            api_password = st.text_input("DataForSEO API Password", value=st.session_state.get("f_pass", "Parmar@5690"), type="password", placeholder="••••••••")

        use_demo = st.checkbox("⚡ Use Instant Demo Mode (Simulates tracking without requiring API credit)", value=False)
        st.caption("Uncheck Demo Mode to run live queries with your DataForSEO credentials.")

        # Section 2: Target Brand Profile
        st.markdown('<div class="section-title" style="margin-top: 15px;"><span class="step-num">2</span> Target Brand Profile</div>', unsafe_allow_html=True)
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            brand_domain = st.text_input("Brand Domain *", value=st.session_state.get("f_domain", "damcogroup.com"), placeholder="damcogroup.com")
        with col_b2:
            brand_name = st.text_input("Brand Name *", value=st.session_state.get("f_name", "Damco Solutions"), placeholder="Damco Solutions")

        col_loc1, col_loc2 = st.columns(2)
        with col_loc1:
            country = st.selectbox("Target Market Country", ["United States", "United Kingdom", "India", "Canada", "Australia"], index=0)
        with col_loc2:
            language = st.selectbox("Target Language", ["en", "es", "fr", "de"], index=0)

        # Section 3: Competitors
        st.markdown('<div class="section-title" style="margin-top: 15px;"><span class="step-num">3</span> Competitor Domains</div>', unsafe_allow_html=True)
        competitors_raw = st.text_area("Competitors (one domain per line)", value=st.session_state.get("f_comps", "suntecindia.com"), height=85, placeholder="suntecindia.com")

        # Section 4: Keywords (Defaults set as requested)
        st.markdown('<div class="section-title" style="margin-top: 15px;"><span class="step-num">4</span> Keywords to Track</div>', unsafe_allow_html=True)
        default_keywords = "top ebook conversion companies for enterprise\ntop data cleansing companies"
        keywords_raw = st.text_area("Search Queries (one per line) *", value=st.session_state.get("f_keywords", default_keywords), height=85, placeholder="top ebook conversion companies for enterprise\ntop data cleansing companies")

        # Submit Button
        submitted = st.form_submit_button("🚀 Run AI Mention Tracker", use_container_width=True)

    if submitted:
        # Validate inputs
        if not brand_domain or not brand_name:
            st.error("Please provide both Brand Domain and Brand Name.")
            st.stop()

        keywords = [k.strip() for k in keywords_raw.split("\n") if k.strip()]
        if not keywords:
            st.error("Please enter at least one keyword to track.")
            st.stop()

        competitors = [c.strip() for c in competitors_raw.split("\n") if c.strip()]

        # Determine Demo vs Live
        if not api_login or not api_password or use_demo:
            is_demo = True
            client = None
        else:
            is_demo = False
            client = DataForSeoClient(api_login, api_password)

        # Create Run in SQLite
        run_id = create_run(brand_domain, brand_name, country, language)
        st.session_state["current_run_id"] = run_id

        # Live Progress UI
        clean_brand_domain = brand_domain.lower()
        clean_brand_name = brand_name.lower()
        clean_competitors = [c.lower() for c in competitors if c.strip()]
        domain_mentions = {domain: 0 for domain in [clean_brand_domain] + clean_competitors}

        platforms = [
            ("google", "Google AI Mode"),
            ("chat_gpt", "ChatGPT"),
            ("perplexity", "Perplexity"),
            ("gemini", "Gemini"),
            ("claude", "Claude")
        ]

        total_steps = len(keywords) * len(platforms)
        current_step = 0

        progress_bar = st.progress(0.0)
        status_box = st.status("🔍 Analyzing AI visibility across models...", expanded=True)

        with status_box:
            for keyword in keywords:
                for platform_key, platform_name in platforms:
                    current_step += 1
                    progress_pct = current_step / total_steps
                    progress_bar.progress(progress_pct)
                    status_box.write(f"[{current_step}/{total_steps}] Querying **{platform_name}** for *'{keyword}'*...")

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
                                result = {
                                    "text": res.get("text", ""),
                                    "sources": res.get("sources", [])
                                }
                            else:
                                err_msg = res.get("error") if res else "No response returned"
                                result = {
                                    "text": f"⚠️ DataForSEO API Notice: {err_msg}",
                                    "sources": []
                                }
                        except Exception as ex:
                            result = {
                                "text": f"⚠️ Query Exception: {ex}",
                                "sources": []
                            }

                    if is_demo or not result:
                        time.sleep(0.3)
                        is_brand_mentioned = random.choice([True, True, False])
                        comp_mentioned = [c for c in clean_competitors if random.choice([True, False])]

                        text_parts = [f"Summary for '{keyword}' on {platform_name}:"]
                        sources = []

                        if is_brand_mentioned:
                            text_parts.append(f"Top recommendations include {brand_name} ({clean_brand_domain}) for enterprise {keyword} solutions.")
                            sources.append(f"https://{clean_brand_domain}/overview")
                        else:
                            text_parts.append(f"Leading platforms evaluated for {keyword}.")

                        for comp in comp_mentioned:
                            text_parts.append(f"Alternative: {comp.capitalize()} ({comp}).")
                            sources.append(f"https://{comp}/features")

                        result = {
                            "text": "\n".join(text_parts),
                            "sources": sources
                        }

                    # Mentions detection
                    text_lower = result["text"].lower()
                    mentioned = clean_brand_domain in text_lower or clean_brand_name in text_lower

                    if mentioned:
                        domain_mentions[clean_brand_domain] += 1

                    competitor_mentions = []
                    for comp in clean_competitors:
                        if comp in text_lower:
                            competitor_mentions.append(comp)
                            domain_mentions[comp] += 1

                    # Discover all other brand domains in text
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

            # Compute Share of Voice
            for domain, mentions in domain_mentions.items():
                sov = (mentions / total_steps) * 100 if total_steps > 0 else 0
                save_competitor_metrics(run_id, domain, mentions, None, round(sov, 1))

            status_box.update(label="✅ Audit Complete! Rendering dashboard...", state="complete")

        st.rerun()
