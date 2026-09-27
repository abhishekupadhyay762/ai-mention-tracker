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
from app import app as flask_app, init_db, create_run, save_result, save_competitor_metrics, get_run, get_results, get_competitor_metrics, get_history, DataForSeoClient

# Explicitly bind template folder path for Jinja2 on Streamlit Cloud (Linux)
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

# Custom CSS to hide Streamlit Chrome & Expand Content to 100% width
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

# Handle Form Submissions via Streamlit query parameters / session state
query_params = st.query_params

if "run_action" in query_params:
    action = query_params["run_action"]
    if action == "reset":
        if "current_run_id" in st.session_state:
            del st.session_state["current_run_id"]
        st.query_params.clear()
        st.rerun()

# Handle POST data from embedded HTML form
if "submit_payload" in st.session_state:
    payload = st.session_state["submit_payload"]
    del st.session_state["submit_payload"]
    
    brand_domain = (payload.get("brand_domain") or "example.com").strip()
    brand_name = (payload.get("brand_name") or "Your Brand").strip()
    country = payload.get("country", "United States")
    language = payload.get("language", "en")
    competitors = payload.get("competitors", [])
    keywords = payload.get("keywords", [])
    use_demo = payload.get("use_demo", True)
    api_login = payload.get("api_login", "")
    api_password = payload.get("api_password", "")

    run_id = create_run(brand_domain, brand_name, country, language)
    st.session_state["current_run_id"] = run_id

    # Run execution
    client = None
    if not use_demo and api_login and api_password:
        client = DataForSeoClient(api_login, api_password)
    else:
        use_demo = True

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

    for keyword in keywords:
        for platform_key, platform_name in platforms:
            current_step += 1

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
                time.sleep(0.05)
                is_brand_mentioned = random.choice([True, True, False])
                comp_mentioned = [c for c in clean_competitors if random.choice([True, False])]

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
            for comp in clean_competitors:
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

    for domain, mentions in domain_mentions.items():
        sov = (mentions / total_steps) * 100 if total_steps > 0 else 0
        save_competitor_metrics(run_id, domain, mentions, None, round(sov, 1))

    st.rerun()

# Display Page View
run_id = st.session_state.get("current_run_id")

with flask_app.test_request_context():
    if run_id:
        run_data = get_run(run_id)
        results = get_results(run_id)
        metrics = get_competitor_metrics(run_id)
        
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
        components.html(rendered_html, height=1350, scrolling=True)
    else:
        rendered_html = render_template("setup.html")
        
        # Inject JS form interceptor to bridge HTML form submission into Streamlit session state
        bridge_script = """
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            const form = document.getElementById('setupForm');
            if(form) {
                form.onsubmit = function(e) {
                    e.preventDefault();
                    const competitors = Array.from(document.querySelectorAll('.competitor-input'))
                        .map(i => i.value.trim())
                        .filter(v => v);
                    const keywords_high = document.getElementById('keywords_high').value.split('\\n').map(k => k.trim()).filter(k => k);
                    const keywords_brand = document.getElementById('keywords_brand').value.split('\\n').map(k => k.trim()).filter(k => k);
                    
                    const payload = {
                        api_login: document.getElementById('api_login').value,
                        api_password: document.getElementById('api_password').value,
                        use_demo: document.getElementById('use_demo').checked,
                        brand_domain: document.getElementById('brand_domain').value,
                        brand_name: document.getElementById('brand_name').value,
                        country: document.getElementById('country').value,
                        language: document.getElementById('language').value,
                        competitors: competitors,
                        keywords: keywords_high.concat(keywords_brand)
                    };

                    window.parent.postMessage({type: 'streamlit_submit', data: payload}, '*');
                }
            }
        });
        </script>
        """
        
        # Add JS event receiver in Streamlit component
        full_html = rendered_html.replace("</body>", bridge_script + "</body>")
        components.html(full_html, height=1100, scrolling=True)

# Streamlit JS Message Listener for Form Submit
st.markdown("""
<script>
window.addEventListener('message', function(event) {
    if (event.data && event.data.type === 'streamlit_submit') {
        const payload = JSON.stringify(event.data.data);
        const input = window.parent.document.querySelector('input[data-testid="stCustomSubmitPayload"]');
        if (input) {
            input.value = payload;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }
});
</script>
""", unsafe_allow_html=True)
