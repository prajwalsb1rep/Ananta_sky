import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# --- CONFIGURATION ---
# PASTE YOUR NEON DATABASE URL HERE
DB_URL = "postgresql://neondb_owner:npg_qkrxJCsVD23N@ep-frosty-truth-a1puejtv-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
CSV_FILE_PATH = "Clean_Dataset.csv"

# Map Kaggle City Names to IATA Codes (Critical for Amadeus compatibility)
CITY_MAP = {
    'Delhi': 'DEL',
    'Mumbai': 'BOM',
    'Bangalore': 'BLR',
    'Hyderabad': 'HYD',
    'Kolkata': 'CCU',
    'Chennai': 'MAA'
}

def seed_database():
    print("🚀 Loading Kaggle dataset...")
    try:
        df = pd.read_csv(CSV_FILE_PATH)
    except FileNotFoundError:
        print("❌ Error: Could not find 'Clean_Dataset.csv'. Make sure it is in the same folder.")
        return

    print(f"📊 Processing {len(df)} rows of flight data...")

    # 1. Clean and Map Cities
    df['source_city'] = df['source_city'].map(CITY_MAP)
    df['destination_city'] = df['destination_city'].map(CITY_MAP)

    # 2. Group by Route & Days Left to find the "Truth"
    # We want to know: For BLR->DEL, 15 days out, what is the avg/min/max?
    baseline = df.groupby(['source_city', 'destination_city', 'days_left'])['price'].agg(
        avg_price='mean',
        min_price='min',
        max_price='max'
    ).reset_index()

    # Round the averages to 2 decimal places
    baseline['avg_price'] = baseline['avg_price'].round(2)

    print(f"🧠 Generated {len(baseline)} unique baseline intelligence points.")

    # 3. Connect to Neon and Insert
    print("🔌 Connecting to Neon Database...")
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()

        # Prepare the query
        insert_query = """
            INSERT INTO baseline_metrics (origin, destination, days_left, avg_price, min_price, max_price)
            VALUES %s
            ON CONFLICT (origin, destination, days_left) DO NOTHING;
        """

        # Convert DataFrame to a list of tuples for fast insertion
        data_tuples = list(baseline.itertuples(index=False, name=None))

        # Execute Batch Insert
        print("💾 Saving knowledge to the database (this may take a moment)...")
        execute_values(cursor, insert_query, data_tuples)
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ SUCCESS! Your Ananta Sky database is now populated with historical intelligence.")
        
    except Exception as e:
        print(f"❌ Database Error: {e}")

if __name__ == "__main__":
    seed_database()
