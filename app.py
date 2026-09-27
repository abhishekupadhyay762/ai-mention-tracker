import os
import sys
import json
import time
import random
import logging
import webbrowser
import threading
from pathlib import Path

# Add current directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify, session, Response, redirect, url_for
from api.dataforseo import DataForSeoClient
import db.storage

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Ensure data directory exists on startup
db.storage.init_db()

@app.route("/")
def index():
    return render_template("setup.html")

@app.route("/api/run", methods=["POST"])
def api_run():
    data = request.json
    
    login = (data.get("api_login") or "").strip()
    password = (data.get("api_password") or "").strip()
    use_demo = data.get("use_demo", False)
    
    if not login or not password or login.lower() == "demo" or password.lower() == "demo":
        use_demo = True

    session["credentials"] = {
        "login": login,
        "password": password
    }
    
    keywords_high = [k.strip() for k in data.get("keywords_high", "").split("\n") if k.strip()]
    keywords_brand = [k.strip() for k in data.get("keywords_brand", "").split("\n") if k.strip()]
    
    session["tracker_config"] = {
        "brand_domain": (data.get("brand_domain") or "example.com").strip(),
        "brand_name": (data.get("brand_name") or "Your Brand").strip(),
        "country": data.get("country", "United States"),
        "language": data.get("language", "en"),
        "competitors": data.get("competitors", []),
        "keywords": keywords_high + keywords_brand,
        "use_demo": use_demo
    }
    
    return jsonify({"status": "ok", "redirect": url_for("running")})

@app.route("/running")
def running():
    if "tracker_config" not in session:
        return redirect(url_for("index"))
    return render_template("running.html")

@app.route("/stream")
def stream():
    config = session.get("tracker_config")
    creds = session.get("credentials")
    
    if not config:
        return Response("data: {\"error\": \"missing_config\"}\n\n", mimetype='text/event-stream')

    run_id = db.storage.create_run(
        config["brand_domain"],
        config["brand_name"],
        config["country"],
        config["language"]
    )
    session["last_run_id"] = run_id

    def generate(config, creds, run_id):
        try:
            is_demo = config.get("use_demo", False)
            login = creds.get("login", "") if creds else ""
            password = creds.get("password", "") if creds else ""
            
            client = None
            if not is_demo and login and password:
                client = DataForSeoClient(login, password)
            else:
                is_demo = True

            keywords = config["keywords"]
            if not keywords:
                keywords = ["digital marketing course"]

            total_steps = len(keywords) * 5
            current_step = 0
            
            platforms = [
                ("google", "Google AI Mode"),
                ("chat_gpt", "ChatGPT"),
                ("perplexity", "Perplexity"),
                ("gemini", "Gemini"),
                ("claude", "Claude")
            ]

            brand_domain = config["brand_domain"].lower()
            brand_name = config["brand_name"].lower()
            competitors = [c.lower() for c in config["competitors"] if c.strip()]
            
            domain_mentions = {domain: 0 for domain in [brand_domain] + competitors}
            
            for keyword in keywords:
                for platform_key, platform_name in platforms:
                    current_step += 1
                    
                    yield f"data: {json.dumps({'step': current_step, 'total': total_steps, 'keyword': keyword, 'platform': platform_name, 'status': 'running'})}\n\n"
                    
                    result = None
                    if not is_demo and client:
                        try:
                            if platform_key == "google":
                                res = client.check_google_ai_mode(keyword, config["country"], config["language"])
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
                                err_msg = res.get("error") if res else "No response returned from API endpoint."
                                result = {
                                    "text": f"⚠️ DataForSEO API Notice: {err_msg}",
                                    "sources": []
                                }
                        except Exception as ex:
                            logging.error(f"Error querying {platform_name}: {ex}")
                            result = {
                                "text": f"⚠️ Query Exception: {ex}",
                                "sources": []
                            }
                    
                    if is_demo or not result:
                        time.sleep(0.25)
                        is_brand_mentioned = random.choice([True, True, False])
                        comp_mentioned = [c for c in competitors if random.choice([True, False])]
                        
                        text_parts = [f"Summary for '{keyword}' on {platform_name}:"]
                        sources = []
                        
                        if is_brand_mentioned:
                            text_parts.append(f"Top recommendation includes {config['brand_name']} ({config['brand_domain']}) for comprehensive {keyword} solutions.")
                            sources.append(f"https://{config['brand_domain']}/overview")
                        else:
                            text_parts.append(f"Leading platforms evaluated for {keyword}.")
                            
                        for comp in comp_mentioned:
                            text_parts.append(f"Alternative: {comp.capitalize()} ({comp}).")
                            sources.append(f"https://{comp}/features")
                            
                        result = {
                            "text": "\n".join(text_parts),
                            "sources": sources
                        }

                    text_lower = result["text"].lower()
                    mentioned = brand_domain in text_lower or brand_name in text_lower
                    
                    if mentioned:
                        domain_mentions[brand_domain] += 1
                        
                    competitor_mentions = []
                    for comp in competitors:
                        if comp in text_lower:
                            competitor_mentions.append(comp)
                            domain_mentions[comp] += 1
                            
                    db.storage.save_result(
                        run_id=run_id,
                        keyword=keyword,
                        platform=platform_key,
                        mentioned=mentioned,
                        mention_position=1 if mentioned else None, 
                        sources_cited=result["sources"],
                        competitor_mentions=competitor_mentions,
                        ai_response_text=result["text"]
                    )
                    
                    status_text = "mentioned" if mentioned else "not mentioned"
                    yield f"data: {json.dumps({'step': current_step, 'total': total_steps, 'keyword': keyword, 'platform': platform_name, 'status': status_text})}\n\n"

            for domain, mentions in domain_mentions.items():
                sov = (mentions / total_steps) * 100 if total_steps > 0 else 0
                db.storage.save_competitor_metrics(run_id, domain, mentions, None, round(sov, 1))

            yield f"data: {json.dumps({'status': 'complete', 'redirect': '/dashboard'})}\n\n"
        except Exception as e:
            logging.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'status': 'complete', 'redirect': '/dashboard', 'warning': str(e)})}\n\n"

    return Response(generate(config, creds, run_id), mimetype='text/event-stream')

@app.route("/dashboard")
def dashboard():
    run_id = session.get("last_run_id")
    if not run_id:
        return redirect(url_for("index"))
        
    run_data = db.storage.get_run(run_id)
    results = db.storage.get_results(run_id)
    metrics = db.storage.get_competitor_metrics(run_id)
    
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
            
    history = db.storage.get_history(run_data["brand_domain"])
            
    return render_template(
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

if __name__ == "__main__":
    def open_browser():
        webbrowser.open("http://127.0.0.1:5001")
        
    print("[*] AI Mention Tracker is running!")
    print("[*] Open in your browser: http://127.0.0.1:5001")
    print("[*] Press Ctrl+C to stop.")
    
    threading.Timer(1.5, open_browser).start()
    app.run(host="127.0.0.1", port=5001)
