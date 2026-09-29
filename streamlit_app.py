import os
import sys
import time
import json
import random
import re
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

# Hide Streamlit chrome, full width
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stHeader"] {display: none;}
    [data-testid="stSidebar"] {display: none;}
    .block-container {
        padding: 0rem !important;
        margin: 0rem !important;
        max-width: 100% !important;
    }
    iframe {
        width: 100% !important;
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)

if "current_run_id" not in st.session_state:
    st.session_state["current_run_id"] = None

if st.session_state["current_run_id"]:
    # ═══════════════════════════ DASHBOARD VIEW ═══════════════════════════
    run_id = st.session_state["current_run_id"]
    
    # Render native reset button at top right
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

else:
    # ═══════════════════════════ SETUP FORM VIEW ═══════════════════════════
    # We create a temporary custom component to render the raw HTML form and securely pass data back to Streamlit
    component_dir = os.path.join(root_dir, "st_setup_component")
    os.makedirs(component_dir, exist_ok=True)
    
    with flask_app.test_request_context():
        rendered_html = render_template("setup.html")
        
        # Inject the Streamlit JS library and our custom submit handler
        new_script = """
<script src="https://cdn.jsdelivr.net/npm/streamlit-component-lib@1.3.0/dist/streamlit.js"></script>
<script>
window.addEventListener('load', function() {
    Streamlit.setComponentReady();
    Streamlit.setFrameHeight(1200);
});

// Overwrite the original submitForm function
async function submitForm(e) {
    e.preventDefault();
    
    const competitors = Array.from(document.querySelectorAll('.competitor-input'))
        .map(i => i.value.trim())
        .filter(v => v);
        
    const data = {
        api_login: document.getElementById('api_login').value,
        api_password: document.getElementById('api_password').value,
        use_demo: document.getElementById('use_demo').checked,
        brand_domain: document.getElementById('brand_domain').value,
        brand_name: document.getElementById('brand_name').value,
        country: document.getElementById('country').value,
        language: document.getElementById('language').value,
        competitors: competitors,
        keywords_high: document.getElementById('keywords_high').value,
        keywords_brand: document.getElementById('keywords_brand').value,
    };
    
    if(!data.use_demo && (!data.api_login.trim() || !data.api_password.trim())) {
        alert("To run Live tracking (Demo Mode unchecked), you must enter your DataForSEO API Login & Password.\\n\\nOtherwise, please keep Demo Mode checked.");
        return;
    }
    
    if(!data.keywords_high.trim() && !data.keywords_brand.trim()) {
        alert("Please enter at least one search query keyword");
        return;
    }
    
    const btn = document.querySelector('button[type="submit"]');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span>⏳ Launching Audit... Please wait</span>';
        btn.style.opacity = '0.7';
    }
    
    // SEND DATA DIRECTLY TO STREAMLIT PYTHON BACKEND
    Streamlit.setComponentValue(data);
}
</script>
        """
        
        # Replace the existing submitForm script tag in setup.html with our Streamlit Component bridge
        rendered_html = re.sub(r'async function submitForm.*?<\/script>', new_script, rendered_html, flags=re.DOTALL)
        
        with open(os.path.join(component_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(rendered_html)
            
    # Declare the custom component and render it
    setup_component = components.declare_component("setup_form", path=component_dir)
    payload = setup_component()
    
    # When payload is received (user clicked Submit)
    if payload:
        brand_domain = (payload.get("brand_domain") or "example.com").strip()
        brand_name = (payload.get("brand_name") or "Your Brand").strip()
        country = payload.get("country", "United States")
        language = payload.get("language", "en")
        competitors = payload.get("competitors", [])
        use_demo = payload.get("use_demo", True)
        api_login = (payload.get("api_login") or "").strip()
        api_password = (payload.get("api_password") or "").strip()

        kw_high = [k.strip() for k in payload.get("keywords_high", "").split("\n") if k.strip()]
        kw_brand = [k.strip() for k in payload.get("keywords_brand", "").split("\n") if k.strip()]
        keywords = kw_high + kw_brand

        if not keywords:
            keywords = ["digital marketing"]

        if not api_login or not api_password:
            use_demo = True

        run_id = create_run(brand_domain, brand_name, country, language)
        
        # Show Loading Progress
        st.write(f"### 🚀 Running Audit for **{brand_name}**...")
        progress_bar = st.progress(0, text="Starting AI Mention Audit...")
        status_box = st.empty()

        client = None
        if not use_demo:
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

        for keyword in keywords:
            for platform_key, platform_name in platforms:
                current_step += 1
                pct = current_step / total_steps
                progress_bar.progress(pct, text=f"[{current_step}/{total_steps}] \"{keyword}\" → {platform_name}...")

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
                            err_msg = res.get("error") if res else "No response"
                            result = {"text": f"⚠️ DataForSEO API Notice: {err_msg}", "sources": []}
                    except Exception as ex:
                        result = {"text": f"⚠️ Query Exception: {ex}", "sources": []}

                if use_demo or not result:
                    time.sleep(0.05)
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

                icon = "✅" if mentioned else "❌"
                status_box.markdown(f"`[{current_step}/{total_steps}]` **{keyword}** → {platform_name} {icon}")

        for domain, mentions in domain_mentions.items():
            sov = (mentions / total_steps) * 100 if total_steps > 0 else 0
            save_competitor_metrics(run_id, domain, mentions, None, round(sov, 1))

        progress_bar.progress(1.0, text="✅ Audit complete! Loading dashboard...")
        time.sleep(0.5)

        st.session_state["current_run_id"] = run_id
        st.rerun()
