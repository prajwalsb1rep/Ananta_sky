import os
import time
import threading
import requests
import psycopg2
import psycopg2.extras
import uvicorn
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

# --- 1. INITIALIZATION ---
mcp = FastMCP("AnantaSky-Agent-1")
# Extract the underlying FastAPI app so we can add a health check
app = mcp._mcp_server.app

# Database Credentials
DB_URL = "postgresql://neondb_owner:npg_qkrxJCsVD23N@ep-frosty-truth-a1puejtv-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

# --- 2. THE SENTINEL (24/7 HEARTBEAT) ---
def self_ping():
    external_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not external_url: return
    print(f"🚀 Sentinel Active: Monitoring {external_url}")
    while True:
        try:
            requests.get(external_url)
        except:
            pass
        time.sleep(600)

@app.get("/health")
def health_check():
    """Standard health check route for Render."""
    return {"status": "alive", "agent": "AnantaSky"}

# --- 3. DATABASE UTILITIES ---
def get_db_connection():
    try:
        return psycopg2.connect(DB_URL)
    except Exception as e:
        print(f"🔥 DB Error: {e}")
        return None

# --- 4. THE AGENT TOOLS ---
@mcp.tool()
def get_active_hunts():
    """[Auto-Pilot] Retrieves active trips and flexibility data."""
    conn = get_db_connection()
    if not conn: return "DB Unavailable."
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT id, origin, destination, travel_date, target_price, flexibility_days FROM watchlist WHERE is_active = TRUE")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r[0], "route": f"{r[1]}->{r[2]}", "date": str(r[3]), "target": float(r[4])} for r in rows]

@mcp.tool()
def analyze_price_safety(origin: str, destination: str, days_left: int):
    """[The Negotiator] Suggests Steal/Fair price bands."""
    conn = get_db_connection()
    if not conn: return "DB Unavailable."
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT avg_price, min_price FROM baseline_metrics WHERE origin = %s AND destination = %s AND days_left = %s", (origin.upper(), destination.upper(), days_left))
    data = cur.fetchone()
    cur.close()
    conn.close()
    if not data: return "No history."
    return {"steal": float(data[1]), "fair": float(data[0])}

@mcp.tool()
def check_market_trends(origin: str, destination: str, lookback_hours: int = 48):
    """[Trend Watcher] Checks price_history for market momentum."""
    conn = get_db_connection()
    if not conn: return "DB Unavailable."
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    query = "SELECT ph.price FROM price_history ph JOIN watchlist w ON ph.route_id = w.id WHERE w.origin = %s AND w.destination = %s AND ph.timestamp > NOW() - INTERVAL '%s hours' ORDER BY ph.timestamp ASC"
    cur.execute(query, (origin.upper(), destination.upper(), str(lookback_hours)))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    if len(rows) < 2: return "No trend data."
    diff = float(rows[-1][0]) - float(rows[0][0])
    return {"trend": "FALLING" if diff < 0 else "RISING", "change": abs(diff)}

# --- 5. EXECUTION ---
if __name__ == "__main__":
    threading.Thread(target=self_ping, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    print(f"✅ Ananta Sky Agent Starting on Port {port}...")
    # Explicitly run the app via uvicorn on all interfaces
    uvicorn.run(app, host="0.0.0.0", port=port)
