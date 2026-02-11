import os
import time
import threading
import requests
import psycopg2
import psycopg2.extras
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mcp.server import Server
from mcp.types import TextContent, Tool

# --- 1. CORE INITIALIZATION ---
app = FastAPI()
mcp_server = Server("AnantaSky-Agent-1")

# Database Credentials
DB_URL = "postgresql://neondb_owner:npg_qkrxJCsVD23N@ep-frosty-truth-a1puejtv-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

# --- 2. THE SENTINEL & HEALTH CHECK ---
@app.get("/health")
async def health():
    """Direct, high-priority route for Render health checks."""
    return {"status": "alive", "timestamp": time.time()}

def self_ping():
    """Keeps the instance from sleeping on Render's free tier."""
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

# --- 4. MCP TOOL DEFINITIONS ---
@mcp_server.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_active_hunts",
            description="[Auto-Pilot] Retrieves all active flight hunts.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="check_market_trends",
            description="[Trend Watcher] Checks if prices are rising or falling.",
            inputSchema={
                "type": "object",
                "properties": {
                    "origin": {"type": "string"},
                    "destination": {"type": "string"}
                }
            }
        )
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    conn = get_db_connection()
    if not conn: return [TextContent(type="text", text="Database offline.")]
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        if name == "get_active_hunts":
            cur.execute("SELECT origin, destination, travel_date, target_price FROM watchlist WHERE is_active = TRUE")
            res = str([dict(r) for r in cur.fetchall()])
        elif name == "check_market_trends":
            # Any-to-Any logic: works for any origin/destination pair
            query = "SELECT ph.price FROM price_history ph JOIN watchlist w ON ph.route_id = w.id WHERE w.origin = %s AND w.destination = %s ORDER BY ph.timestamp DESC LIMIT 5"
            cur.execute(query, (arguments['origin'].upper(), arguments['destination'].upper()))
            res = str([r[0] for r in cur.fetchall()])
        else:
            res = "Tool not found."
    finally:
        cur.close()
        conn.close()
    
    return [TextContent(type="text", text=res)]

# --- 5. THE MCP COMMUNICATION BRIDGE ---
@app.post("/messages")
async def handle_messages(request: Request):
    """The main endpoint where Groq sends instructions."""
    payload = await request.json()
    response = await mcp_server.handle_request(payload)
    return JSONResponse(content=response)

# --- 6. EXECUTION ---
if __name__ == "__main__":
    # Start Heartbeat in background
    threading.Thread(target=self_ping, daemon=True).start()
    
    # Bind to 0.0.0.0 and use the port assigned by Render
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Ananta Sky Agent LIVE on Port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
