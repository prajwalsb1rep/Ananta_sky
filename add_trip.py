import psycopg2
import sys
from datetime import datetime

# --- CONFIGURATION ---
# Your Prajwal Labs Connection String
DB_URL = "postgresql://neondb_owner:npg_qkrxJCsVD23N@ep-frosty-truth-a1puejtv-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

def add_trip_to_db(origin, destination, travel_date, target_price, whatsapp, flex_days):
    print(f"\n⚙️  Connecting to Ananta Sky Database...")
    
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()

        # Logic: If flex_days > 0, it is a "Flexible" trip.
        is_flexible_bool = True if flex_days > 0 else False

        query = """
            INSERT INTO watchlist 
            (origin, destination, travel_date, flexibility_days, is_flexible, target_price, user_whatsapp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """
        
        cursor.execute(query, (
            origin.upper(), 
            destination.upper(), 
            travel_date, 
            flex_days,
            is_flexible_bool, 
            target_price, 
            whatsapp
        ))
        
        new_id = cursor.fetchone()[0]
        conn.commit()
        
        print(f"\n✅ SUCCESS! Trip ID {new_id} is live.")
        if is_flexible_bool:
             print(f"📅 Strategy: FLEXIBLE. Watching {travel_date} (+/- {flex_days} days).")
        else:
             print(f"📅 Strategy: SNIPER. Watching ONLY {travel_date}.")
        
        print(f"💰 Target: We will alert {whatsapp} if price < ₹{target_price}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"\n❌ Database Error: {e}")

def get_user_input():
    print("\n--- ✈️  ANANTA SKY: NEW TRIP SETUP ✈️  ---")
    
    # 1. Get Route
    origin = input("📍 Enter Origin Code (e.g., BLR): ").strip().upper()
    dest = input("📍 Enter Destination Code (e.g., DEL): ").strip().upper()
    
    # 2. Get Date
    while True:
        date_str = input("📅 Enter Travel Date (YYYY-MM-DD): ").strip()
        try:
            # Validate format
            datetime.strptime(date_str, "%Y-%m-%d")
            break
        except ValueError:
            print("❌ Invalid format. Please use YYYY-MM-DD (e.g., 2026-11-24)")

    # 3. Get Price
    try:
        price = float(input("💰 Enter Your Budget (₹): "))
    except ValueError:
        print("❌ Price must be a number.")
        return

    # 4. Get Flexibility
    flex_input = input("🔀 Are your dates flexible? (yes/no): ").lower()
    flex_days = 0
    if flex_input in ['yes', 'y']:
        try:
            flex_days = int(input("   How many days +/- can you shift? (e.g., 3): "))
        except ValueError:
            flex_days = 3 # Default to 3 if they type nonsense
            print("   (Defaulting to +/- 3 days)")

    # 5. Get WhatsApp
    # You can hardcode your number here to save time, or ask for it.
    whatsapp = input("📱 Enter WhatsApp Number (+91...): ").strip()
    if not whatsapp:
        whatsapp = "+919999999999" # Placeholder default

    # Execute
    add_trip_to_db(origin, dest, date_str, price, whatsapp, flex_days)

if __name__ == "__main__":
    get_user_input()
