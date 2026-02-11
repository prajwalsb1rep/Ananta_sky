import os
import time
import threading
import requests
import psycopg2
import psycopg2.extras
import uvicorn
from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse
from mcp.server import Server
from mcp.types import TextContent, Tool

# --- 1. INITIALIZATION (THE STABLE WAY) ---
# We use the base Server class directly
app = FastAPI()
mcp_server = Server("AnantaSky-Agent-1")

# Database Credentials
DB_URL = "postgresql://neondb_owner:npg_qkrxJCsVD23N@ep-frosty-truth-a1puejtv-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

# --- 2. THE SENTINEL (24/7 HEARTBEAT) ---
def self_ping():
    external_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not external_url: return
    while True:
        try:
            requests.get(external_url + "/health")
        except:
            pass
        time.sleep(600)

@app.get("/health")
async def health():
    return {"status": "alive"}

# --- 3. DATABASE UTILITIES ---
def get_db_connection():
    try:
        return psycopg2.connect(DB_URL)
    except Exception as e:
        print(f"🔥 DB Error: {e}")
        return None

# --- 4. THE AGENT TOOLS (MAPPED MANUALLY FOR STABILITY) ---

@mcp_server.list_tools()
async def list_tools():
    """Defines the tools available to Groq."""
    return [
        Tool(
            name="get_active_hunts",
            description="[Auto-Pilot] Retrieves active trips for monitoring.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="analyze_price_safety",
            description="[The Negotiator] Pulls Kaggle metrics for price bands.",
            inputSchema={
                "type": "object",
                "properties": {
                    "origin": {"type": "string"},
                    "destination": {"type": "string"},
                    "days_left": {"type": "integer"}
                }
            }
        )
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Executes the database logic for each tool."""
    conn = get_db_connection()
    if not conn: return [TextContent(type="text", text="DB Error")]
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    if name == "get_active_hunts":
        cur.execute("SELECT origin, destination, travel_date FROM watchlist WHERE is_active = TRUE")
        rows = cur.fetchall()
        res = str([dict(r) for r in rows])
    elif name == "analyze_price_safety":
        cur.execute("SELECT avg_price, min_price FROM baseline_metrics WHERE origin = %s AND destination = %s AND days_left = %s", 
                    (arguments['origin'].upper(), arguments['destination'].upper(), arguments['days_left']))
        row = cur.fetchone()
        res = str(dict(row)) if row else "No data"
    
    cur.close()
    conn.close()
    return [TextContent(type="text", text=res)]

# --- 5. THE TRANSPORT BRIDGE (SSE) ---
# This manual route replaces the broken 'StarletteServerTransport'
@app.get("/sse")
async def sse(request: Request):
    async def event_generator():
        # This keeps the connection open for the AI
        yield {"data": "connected"}
        while True:
            if await request.is_disconnected(): break
            time.sleep(1)
    return EventSourceResponse(event_generator())

@app.post("/messages")
async def messages(request: Request):
    # This handles the actual tool requests
    return await mcp_server.handle_request(await request.json())

# --- 6. EXECUTION ---
if __name__ == "__main__":
    threading.Thread(target=self_ping, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Ananta Sky LIVE on Port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
