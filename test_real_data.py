import os
import json
from data_aggregator import aggregator
from tactical_engine import compute_tactical_summary_from_scraping
from visuals import generate_all_graphics
from datetime import datetime, timedelta

def main():
    # Try to find a finished match from the last few days
    for days_ago in range(1, 7):
        date_str = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        print(f"Fetching fixtures for {date_str}...")
        fixtures = aggregator.get_daily_fixtures(date_str=date_str, major_only=True)
        finished_matches = [f for f in fixtures if f['fixture']['status_type'] == 'finished']
        
        if finished_matches:
            break
            
    if not finished_matches:
        print("No finished matches found in recent days.")
        return
        
    # Pick the first finished match
    match = finished_matches[0]
    match_id = match['fixture']['id']
    home = match['teams']['home']['name']
    away = match['teams']['away']['name']
    print(f"Selected match: {home} vs {away} (ID: {match_id})")
    
    print("Fetching deep data from SofaScore...")
    raw_data = aggregator.get_match_all_data(match_id)
    
    print("Computing tactical summary...")
    summary = compute_tactical_summary_from_scraping(raw_data)
    
    output_dir = os.path.join(os.path.dirname(__file__), "outputs")
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Generating graphics to {output_dir}...")
    generate_all_graphics(summary, save_dir=output_dir)
    print("Done! Real data graphics generated successfully.")

if __name__ == "__main__":
    main()
