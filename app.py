import os
import sys
import json
import time
import random
import logging
import base64
import sqlite3
import requests
import webbrowser
import threading
from pathlib import Path
from datetime import datetime

# Guarantee project root and cwd are in sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
cwd = os.getcwd()
if cwd not in sys.path:
    sys.path.insert(0, cwd)

from flask import Flask, render_template, request, jsonify, session, Response, redirect, url_for

import re

def extract_urls_from_text(text):
    if not text:
        return []
    raw_urls = re.findall(r'https?://[^\s\)\]\>"\']+', text)
    cleaned_urls = []
    for url in raw_urls:
        url_clean = url.rstrip('.,;:)]>')
        if url_clean and url_clean not in cleaned_urls:
            cleaned_urls.append(url_clean)
    return cleaned_urls

def extract_domains_from_text(text):
    if not text:
        return []
    found_domains = set()
    domains = re.findall(r'\b[a-zA-Z0-9-]+\.(?:com|org|net|io|in|co|ai|uk|ca|gov|edu|me|app)\b', text.lower())
    ignored_domains = {"schema.org", "w3.org", "google.com", "wikipedia.org", "github.com", "twitter.com", "facebook.com", "linkedin.com", "schema.org"}
    for d in domains:
        if d not in ignored_domains:
            found_domains.add(d)
    return list(found_domains)

# DataForSEO API Client
class DataForSeoClient:
    def __init__(self, login, password):
        self.login = (login or "").strip()
        self.password = (password or "").strip()
        self.base_url = "https://api.dataforseo.com/v3"
        credentials = f"{self.login}:{self.password}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        self.headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/json'
        }

    def _make_request(self, endpoint, payload):
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.post(url, headers=self.headers, json=[payload], timeout=25)
            if response.status_code == 200:
                res = response.json()
                status_code = res.get("status_code")
                status_msg = res.get("status_message", "")
                if status_code != 20000:
                    logging.warning(f"DataForSEO API status {status_code}: {status_msg}")
                    return {"error": f"DataForSEO API Error {status_code}: {status_msg}", "raw": res}
                return {"data": res, "error": None}
            elif response.status_code in (401, 402, 403):
                try:
                    res_json = response.json()
                    detail = res_json.get("status_message") or response.text
                except Exception:
                    detail = response.text
                err_msg = f"DataForSEO HTTP {response.status_code}: {detail}"
                logging.error(err_msg)
                return {"error": err_msg, "raw": response.text}
            else:
                err_msg = f"DataForSEO API HTTP Error {response.status_code}: {response.text}"
                logging.error(err_msg)
                return {"error": err_msg, "raw": response.text}
        except Exception as e:
            err_msg = f"Request Failed: {e}"
            logging.error(err_msg)
            return {"error": err_msg, "raw": None}

    def check_google_ai_mode(self, keyword, location_name="United States", language_code="en"):
        res = self._make_request("serp/google/ai_mode/live/advanced", {
            "keyword": keyword,
            "location_name": location_name,
            "language_code": language_code
        })
        
        if res.get("error"):
            res_org = self._make_request("serp/google/organic/live/advanced", {
                "keyword": keyword,
                "location_name": location_name,
                "language_code": language_code
            })
            if res_org.get("error"):
                return {"error": res.get("error")}
            res = res_org

        data = res.get("data")
        if not data or not data.get("tasks"):
            return {"error": "No task results returned from DataForSEO"}
            
        try:
            task = data["tasks"][0]
            if task.get("status_code") != 20000:
                return {"error": f"Task Status {task.get('status_code')}: {task.get('status_message')}"}
                
            results_list = task.get("result") or []
            if not results_list:
                return {"error": "Empty result from Google SERP"}
            
            first_result = results_list[0] if results_list else {}
            items = first_result.get("items") or []
            if not items:
                return {"error": "Empty result items from Google SERP"}

            full_text = []
            sources = []
            
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("type", "")
                if item_type in ("ai_overview", "ai_overview_element"):
                    if item.get("markdown"):
                        full_text.append(str(item["markdown"]))
                    elif item.get("text"):
                        full_text.append(str(item["text"]))
                    references = item.get("references") or []
                    for ref in references:
                        if isinstance(ref, dict) and ref.get("url"):
                            sources.append(ref["url"])
                elif item_type == "organic":
                    title = item.get("title", "") or ""
                    snippet = item.get("description", "") or item.get("snippet", "") or ""
                    url = item.get("url", "") or ""
                    if title or snippet:
                        full_text.append(f"- **{title}**: {snippet}")
                    if url:
                        sources.append(url)

            combined_text = "\n\n".join(full_text)
            if not combined_text:
                return {"error": "No text extracted from SERP items"}

            # Regex extract all URLs from text
            text_urls = extract_urls_from_text(combined_text)
            all_sources = list(dict.fromkeys(sources + text_urls))

            return {
                "text": combined_text[:4000],
                "sources": all_sources[:15],
                "error": None
            }
        except Exception as ex:
            return {"error": f"Parsing Error: {ex}"}

    def check_chatgpt(self, keyword):
        return self._check_llm("ai_optimization/chat_gpt/llm_responses/live", keyword, model_name="gpt-4.1-mini")

    def check_perplexity(self, keyword):
        return self._check_llm("ai_optimization/perplexity/llm_responses/live", keyword, model_name="sonar")

    def check_gemini(self, keyword):
        return self._check_llm("ai_optimization/gemini/llm_responses/live", keyword, model_name="gemini-2.5-flash-lite")

    def check_claude(self, keyword):
        return self._check_llm("ai_optimization/claude/llm_responses/live", keyword, model_name="claude-haiku-4-5")

    def _check_llm(self, endpoint, keyword, model_name=None):
        payload = {
            "user_prompt": f"What are the top recommended companies, services, and websites for: '{keyword}'? Provide exact brand names, official domain names, and website URLs.",
            "web_search": True,
            "max_output_tokens": 1000
        }
        if model_name:
            payload["model_name"] = model_name

        # Try up to 2 times with delay on rate limit
        for attempt in range(2):
            res = self._make_request(endpoint, payload)
            if res.get("error"):
                return {"error": res.get("error")}
                
            data = res.get("data")
            if not data or not data.get("tasks"):
                return {"error": "No task results returned from DataForSEO LLM API"}
                
            try:
                task = data["tasks"][0]
                task_status = task.get("status_code")
                # Rate limit — wait and retry once
                if task_status == 50301 and attempt == 0:
                    logging.warning(f"Rate limited on {endpoint}, retrying in 5s...")
                    time.sleep(5)
                    continue
                if task_status != 20000:
                    return {"error": f"LLM Task Error {task_status}: {task.get('status_message')}"}
                
                results = task.get("result") or []
                if not results:
                    return {"error": "Empty result from LLM API"}
                
                first_result = results[0] if results else {}
                items = first_result.get("items") or []
                if not items:
                    return {"error": "Empty items returned from LLM API"}

                full_text = []
                sources = []
                
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    if item.get("response"):
                        full_text.append(str(item["response"]))
                    if item.get("text"):
                        full_text.append(str(item["text"]))
                    if item.get("markdown"):
                        full_text.append(str(item["markdown"]))
                        
                    sections = item.get("sections") or []
                    for section in sections:
                        if not isinstance(section, dict):
                            continue
                        if section.get("text"):
                            full_text.append(str(section["text"]))
                        annotations = section.get("annotations") or []
                        for annotation in annotations:
                            if isinstance(annotation, dict) and annotation.get("url"):
                                sources.append(annotation["url"])
                                
                    references = item.get("references") or []
                    for ref in references:
                        if isinstance(ref, dict) and ref.get("url"):
                            sources.append(ref["url"])

                combined_text = "\n\n".join(full_text)
                if not combined_text:
                    return {"error": "No response text found from LLM API"}

                # Regex extract all URLs from response text
                text_urls = extract_urls_from_text(combined_text)
                all_sources = list(dict.fromkeys(sources + text_urls))

                return {
                    "text": combined_text,
                    "sources": all_sources[:15],
                    "error": None
                }
            except Exception as ex:
                return {"error": f"Parsing Error: {ex}"}
        
        return {"error": "Rate limit exceeded after retry"}

# SQLite Database Layer
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "tracker.db"

def get_db_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_domain TEXT NOT NULL,
            brand_name TEXT NOT NULL,
            country TEXT NOT NULL,
            language TEXT NOT NULL,
            run_date DATETIME NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mention_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            keyword TEXT NOT NULL,
            platform TEXT NOT NULL,
            mentioned BOOLEAN,
            mention_position INTEGER,
            sources_cited TEXT,
            competitor_mentions TEXT,
            ai_response_text TEXT,
            timestamp DATETIME NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs (id)
        );
        CREATE TABLE IF NOT EXISTS competitor_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            domain TEXT NOT NULL,
            total_mentions INTEGER NOT NULL,
            avg_position REAL,
            share_of_voice REAL,
            FOREIGN KEY (run_id) REFERENCES runs (id)
        );
    ''')
    conn.commit()
    conn.close()

def create_run(brand_domain, brand_name, country, language):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO runs (brand_domain, brand_name, country, language, run_date) VALUES (?, ?, ?, ?, ?)",
        (brand_domain, brand_name, country, language, datetime.now())
    )
    run_id = c.lastrowid
    conn.commit()
    conn.close()
    return run_id

def save_result(run_id, keyword, platform, mentioned, mention_position, sources_cited, competitor_mentions, ai_response_text):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO mention_results 
           (run_id, keyword, platform, mentioned, mention_position, sources_cited, competitor_mentions, ai_response_text, timestamp) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (run_id, keyword, platform, mentioned, mention_position, json.dumps(sources_cited), json.dumps(competitor_mentions), ai_response_text, datetime.now())
    )
    conn.commit()
    conn.close()

def save_competitor_metrics(run_id, domain, total_mentions, avg_position, share_of_voice):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO competitor_metrics (run_id, domain, total_mentions, avg_position, share_of_voice) 
           VALUES (?, ?, ?, ?, ?)""",
        (run_id, domain, total_mentions, avg_position, share_of_voice)
    )
    conn.commit()
    conn.close()

def get_run(run_id):
    conn = get_db_connection()
    run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    conn.close()
    return dict(run) if run else None

def get_results(run_id):
    conn = get_db_connection()
    results = conn.execute("SELECT * FROM mention_results WHERE run_id = ?", (run_id,)).fetchall()
    conn.close()
    return [dict(r) for r in results]

def get_competitor_metrics(run_id):
    conn = get_db_connection()
    metrics = conn.execute("SELECT * FROM competitor_metrics WHERE run_id = ?", (run_id,)).fetchall()
    conn.close()
    return [dict(m) for m in metrics]

def get_history(brand_domain):
    conn = get_db_connection()
    runs = conn.execute("SELECT * FROM runs WHERE brand_domain = ? ORDER BY run_date ASC", (brand_domain,)).fetchall()
    history = []
    for run in runs:
        metrics = conn.execute("SELECT * FROM competitor_metrics WHERE run_id = ?", (run['id'],)).fetchall()
        history.append({
            'run': dict(run),
            'metrics': [dict(m) for m in metrics]
        })
    conn.close()
    return history

# Create storage object namespace for backwards compatibility
class StorageNamespace:
    init_db = staticmethod(init_db)
    create_run = staticmethod(create_run)
    save_result = staticmethod(save_result)
    save_competitor_metrics = staticmethod(save_competitor_metrics)
    get_run = staticmethod(get_run)
    get_results = staticmethod(get_results)
    get_competitor_metrics = staticmethod(get_competitor_metrics)
    get_history = staticmethod(get_history)

storage = StorageNamespace()

# Flask App Initialization with explicit absolute template folder path
template_dir = os.path.join(root_dir, "templates")
if not os.path.exists(template_dir):
    os.makedirs(template_dir, exist_ok=True)

app = Flask(__name__, template_folder=template_dir)
app.secret_key = os.urandom(24)

# Ensure database exists
init_db()

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

    run_id = create_run(
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

                    # Dynamically discover all other brand domains present in AI response text
                    discovered_domains = extract_domains_from_text(result["text"])
                    for dom in discovered_domains:
                        if dom != brand_domain and dom not in competitor_mentions and dom not in competitors:
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
                    
                    status_text = "mentioned" if mentioned else "not mentioned"
                    yield f"data: {json.dumps({'step': current_step, 'total': total_steps, 'keyword': keyword, 'platform': platform_name, 'status': status_text})}\n\n"

            for domain, mentions in domain_mentions.items():
                sov = (mentions / total_steps) * 100 if total_steps > 0 else 0
                save_competitor_metrics(run_id, domain, mentions, None, round(sov, 1))

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
