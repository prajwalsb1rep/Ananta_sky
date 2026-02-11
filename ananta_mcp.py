import os
import time
import threading
import requests
import psycopg2
import psycopg2.extras
import uvicorn # We use this to launch the server explicitly
from mcp.server.fastmcp import FastMCP

# --- 1. INITIALIZATION ---
# We initialize the MCP Server. 
mcp = FastMCP("AnantaSky-Agent-1")

# Database Credentials
DB_URL = "postgresql://neondb_owner:npg_qkrxJCsVD23N@ep-frosty-truth-a1puejtv-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

# --- 2. THE SENTINEL (24/7 HEARTBEAT) ---
def self_ping():
    """Pings the server's own URL every 10 minutes to stay awake on Render."""
    external_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not external_url:
        print("⚠️ No RENDER_EXTERNAL_URL found. Self-ping inactive.")
        return

    print(f"🚀 Sentinel Active: Monitoring {external_url}")
    while True:
        try:
            # We ping the health check or root
            response = requests.get(external_url)
            # We don't print 200 OK to keep logs clean
        except Exception as e:
            print(f"❌ Heartbeat Error: {e}")
        time.sleep(600)

def start_heartbeat():
    """Runs the Sentinel in a background thread."""
    thread = threading.Thread(target=self_ping, daemon=True)
    thread.start()

# --- 3. DATABASE UTILITIES ---
def get_db_connection():
    """Robust connection to Neon Postgres."""
    try:
        conn = psycopg2.connect(DB_URL)
        return conn
    except Exception as e:
        print(f"🔥 DB Error: {e}")
        return None

# --- 4. THE AGENT TOOLS ---

@mcp.tool()
def get_active_hunts():
    """[Auto-Pilot] Retrieves active trips and flexibility data from the database."""
    conn = get_db_connection()
    if not conn: return "DB Unavailable."
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT id, origin, destination, travel_date, target_price, flexibility_days FROM watchlist WHERE is_active = TRUE")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{
            "hunt_id": r['id'], 
            "route": f"{r['origin']}->{r['destination']}", 
            "date": str(r['travel_date']), 
            "target": float(r['target_price']), 
            "flex": r['flexibility_days']
        } for r in rows]
    except Exception as e: return f"Retrieval failed: {e}"

@mcp.tool()
def analyze_price_safety(origin: str, destination: str, days_left: int):
    """[The Negotiator] Suggests Steal/Fair/Rip-off price bands."""
    conn = get_db_connection()
    if not conn: return "DB Unavailable."
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = "SELECT avg_price, min_price FROM baseline_metrics WHERE origin = %s AND destination = %s AND days_left = %s"
        cur.execute(query, (origin.upper(), destination.upper(), days_left))
        data = cur.fetchone()
        cur.close()
        conn.close()
        if not data: return "No history found."
        min_p = float(data['min_price'])
        avg_p = float(data['avg_price'])
        return {
            "steal_zone": f"₹{min_p} - ₹{min_p * 1.1:.0f}",
            "fair_zone": f"₹{min_p * 1.1:.0f} - ₹{avg_p:.0f}",
            "average": avg_p
        }
    except Exception as e: return f"Analysis failed: {e}"

@mcp.tool()
def check_market_trends(origin: str, destination: str, lookback_hours: int = 48):
    """[Trend Watcher] Checks price_history for rising/falling trends."""
    conn = get_db_connection()
    if not conn: return "DB Unavailable."
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """
            SELECT ph.price FROM price_history ph 
            JOIN watchlist w ON ph.route_id = w.id 
            WHERE w.origin = %s AND w.destination = %s 
            AND ph.timestamp > NOW() - INTERVAL '%s hours' 
            ORDER BY ph.timestamp ASC
        """
        cur.execute(query, (origin.upper(), destination.upper(), str(lookback_hours)))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        if len(rows) < 2: return "Insufficient data for trend."
        diff = float(rows[-1][0]) - float(rows[0][0])
        return {"trend": "FALLING" if diff < 0 else "RISING" if diff > 0 else "STABLE", "change": abs(diff)}
    except Exception as e: return f"Trend check failed: {e}"

# --- 5. EXECUTION (THE FIX) ---
if __name__ == "__main__":
    # Start the Sentinel
    start_heartbeat()
    
    # Get the PORT from Render (default 10000)
    port = int(os.environ.get("PORT", 10000))
    print(f"✅ Ananta Sky Agent Starting on Port {port}...")

    # RAM'S FIX: 
    # Instead of mcp.run() which is broken for cloud binding,
    # we explicitly use uvicorn to run the internal MCP app.
    # This guarantees we can bind to 0.0.0.0.
    
    # 1. Start the server logic
    # 2. Bind to 0.0.0.0 (Required for Render)
    # 3. Use the correct port
    uvicorn.run(mcp._mcp_server.app, host="0.0.0.0", port=port)
