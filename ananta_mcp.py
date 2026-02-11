import os
import time
import threading
import requests
import psycopg2
import psycopg2.extras
from mcp.server.fastmcp import FastMCP

# --- CONFIGURATION & SETUP ---
# Initialize the MCP Server with a professional name
mcp = FastMCP("AnantaSky-Agent-1")

# Database Credentials (Securely connected to your Neon Project)
DB_URL = "postgresql://neondb_owner:npg_qkrxJCsVD23N@ep-frosty-truth-a1puejtv-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

# --- 1. THE SENTINEL (24/7 HEARTBEAT LOGIC) ---
def self_ping():
    """
    Background process: Pings the server's own URL every 10 minutes.
    This prevents the free Render instance from 'sleeping' (spinning down).
    """
    # You will add this URL in the Render Dashboard later
    external_url = os.environ.get("RENDER_EXTERNAL_URL")
    
    if not external_url:
        print("⚠️ No RENDER_EXTERNAL_URL found. Self-ping disabled (OK for local testing).")
        return

    print(f"🚀 Sentinel Active: Monitoring {external_url}")
    while True:
        try:
            # We ping the /sse endpoint or just the root to keep it awake
            response = requests.get(f"{external_url}")
            if response.status_code != 200:
                print(f"⚠️ Heartbeat Warning: Status {response.status_code}")
        except Exception as e:
            print(f"❌ Heartbeat Error: {e}")
        
        # Sleep for 10 minutes (600 seconds)
        time.sleep(600)

def start_heartbeat():
    """Launches the Sentinel in a separate thread so it doesn't block the Agent."""
    thread = threading.Thread(target=self_ping, daemon=True)
    thread.start()


# --- 2. DATABASE UTILITIES ---
def get_db_connection():
    """Establishes a robust connection to Neon Postgres."""
    try:
        conn = psycopg2.connect(DB_URL)
        return conn
    except Exception as e:
        print(f"🔥 Critical Database Error: {e}")
        return None


# --- 3. THE AGENT TOOLS (SKILLS) ---

@mcp.tool()
def get_active_hunts():
    """
    [Use Case: Auto-Pilot & Flex-Seeker]
    Retrieves the list of trips Ananda wants to track. 
    Includes flexibility logic (+/- days) and active status.
    """
    conn = get_db_connection()
    if not conn: return "System Error: Database unavailable."

    try:
        # DictCursor lets us access data by column name (e.g., row['origin'])
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        query = """
            SELECT id, origin, destination, travel_date, target_price, flexibility_days, is_active
            FROM watchlist 
            WHERE is_active = TRUE
        """
        cur.execute(query)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # Transform into clean JSON for the AI
        hunts = []
        for r in rows:
            hunts.append({
                "hunt_id": r['id'],
                "route": f"{r['origin']} -> {r['destination']}",
                "date": str(r['travel_date']),
                "target": float(r['target_price']),
                "flexibility": f"+/- {r['flexibility_days']} days" if r['flexibility_days'] else "Exact Date (Sniper)",
                "mode": "Auto-Pilot"  # Context for the AI
            })
        return hunts

    except Exception as e:
        return f"Error retrieval failed: {e}"


@mcp.tool()
def analyze_price_safety(origin: str, destination: str, days_left: int):
    """
    [Use Case: The Negotiator & Price Bands]
    Analyzes historical data to tell the user what a 'Fair' price is vs. a 'Steal'.
    Used when the user asks: "What should I pay for this flight?"
    """
    conn = get_db_connection()
    if not conn: return "System Error: Database unavailable."

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Pulls from the 1,470 Kaggle Intelligence Points
        query = """
            SELECT avg_price, min_price, max_price 
            FROM baseline_metrics 
            WHERE origin = %s AND destination = %s AND days_left = %s
        """
        cur.execute(query, (origin.upper(), destination.upper(), days_left))
        data = cur.fetchone()
        cur.close()
        conn.close()

        if not data:
            return "No historical data found. Recommend initiating 'Explorer Mode' to gather fresh data."

        avg_p = float(data['avg_price'])
        min_p = float(data['min_price'])

        # Logic: Define the "Bands" for the User
        return {
            "advice": "Here is the Price Band analysis for your negotiation.",
            "steal_zone": f"₹{min_p} - ₹{min_p * 1.1:.0f}",  # Lowest to +10%
            "fair_zone": f"₹{min_p * 1.1:.0f} - ₹{avg_p:.0f}", # +10% to Average
            "rip_off_zone": f"Above ₹{avg_p:.0f}",
            "historical_average": avg_p
        }

    except Exception as e:
        return f"Analysis failed: {e}"


@mcp.tool()
def check_market_trends(origin: str, destination: str, lookback_hours: int = 48):
    """
    [Use Case: Trend Watcher]
    Checks the 'price_history' table to see if prices are Rising, Falling, or Stable.
    Crucial for deciding *when* to alert (e.g., "Wait, it's dropping!").
    """
    conn = get_db_connection()
    if not conn: return "System Error: Database unavailable."

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get the recent price logs for this route
        query = """
            SELECT ph.price, ph.timestamp 
            FROM price_history ph
            JOIN watchlist w ON ph.route_id = w.id
            WHERE w.origin = %s AND w.destination = %s
            AND ph.timestamp > NOW() - INTERVAL '%s hours'
            ORDER BY ph.timestamp ASC
        """
        cur.execute(query, (origin.upper(), destination.upper(), str(lookback_hours)))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if len(rows) < 2:
            return "Not enough data points to determine a trend yet."

        start_price = float(rows[0]['price'])
        current_price = float(rows[-1]['price'])
        
        # Calculate Trend
        diff = current_price - start_price
        if diff < 0:
            trend = "FALLING 📉"
            advice = "Hold. The market is cooling down."
        elif diff > 0:
            trend = "RISING 📈"
            advice = "Alert Immediately. The window is closing."
        else:
            trend = "STABLE ➡️"
            advice = "Monitor. No sudden movements."

        return {
            "market_trend": trend,
            "change_amount": f"₹{abs(diff)}",
            "ai_advice": advice,
            "last_check": str(rows[-1]['timestamp'])
        }

    except Exception as e:
        return f"Trend analysis failed: {e}"

# --- 4. EXECUTION (The Corrected Part) ---
if __name__ == "__main__":
    # Start the Sentinel first to keep the app awake
    print("🤖 Ananta Sky Agent: Initializing...")
    start_heartbeat()
    
    # 1. GET PORT: Render provides a PORT environment variable. We default to 8000 for local testing.
    port = int(os.environ.get("PORT", 8000))
    
    # 2. RUN SERVER: We MUST use '0.0.0.0' and 'sse' transport for Render Web Services
    print(f"✅ MCP Server Starting on Port {port}...")
    mcp.run(transport="sse", host="0.0.0.0", port=port)
