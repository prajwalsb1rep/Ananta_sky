import os
import time
import threading
import requests
import psycopg2
import psycopg2.extras
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# --- 1. CORE ARCHITECTURE ---
app = FastAPI()

# Database Credentials
DB_URL = "postgresql://neondb_owner:npg_qkrxJCsVD23N@ep-frosty-truth-a1puejtv-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

# --- 2. THE SENTINEL & HEALTH CHECK ---
@app.get("/health")
async def health():
    return {"status": "alive", "agent": "AnantaSky", "timestamp": time.time()}

def self_ping():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url: return
    while True:
        try:
            requests.get(f"{url}/health")
        except: pass
        time.sleep(600)

# --- 3. DATABASE UTILITIES ---
def get_db_connection():
    try:
        return psycopg2.connect(DB_URL)
    except Exception as e:
        print(f"🔥 DB Error: {e}")
        return None

# --- 4. THE AGENT INTELLIGENCE (ANY-TO-ANY TOOLS) ---

@app.post("/messages")
async def handle_tool_call(request: Request):
    data = await request.json()
    tool_name = data.get("name")
    args = data.get("arguments", {})
    
    conn = get_db_connection()
    if not conn: return {"error": "Database offline"}
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        if tool_name == "get_active_hunts":
            cur.execute("SELECT origin, destination, travel_date, target_price FROM watchlist WHERE is_active = TRUE")
            result = [dict(r) for r in cur.fetchall()]
        
        elif tool_name == "analyze_price_safety":
            cur.execute("SELECT avg_price, min_price FROM baseline_metrics WHERE origin = %s AND destination = %s AND days_left = %s", 
                        (args['origin'].upper(), args['destination'].upper(), args['days_left']))
            row = cur.fetchone()
            result = dict(row) if row else {"message": "No history"}

        elif tool_name == "check_market_trends":
            # TIME-SERIES LOGIC
            query = """
                SELECT ph.price FROM price_history ph 
                JOIN watchlist w ON ph.route_id = w.id 
                WHERE w.origin = %s AND w.destination = %s 
                ORDER BY ph.timestamp DESC LIMIT 10
            """
            cur.execute(query, (args['origin'].upper(), args['destination'].upper()))
            rows = cur.fetchall()
            # SAFETY FIX: Ensure we return a list of floats, or an empty list if no data
            result = [float(r[0]) for r in rows] if rows else []
        
        else:
            result = "Unknown Tool"
            
    finally:
        cur.close()
        conn.close()
        
    return {"result": result}

# --- 5. EXECUTION ---
if __name__ == "__main__":
    threading.Thread(target=self_ping, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Ananta Sky Agent LIVE on Port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
