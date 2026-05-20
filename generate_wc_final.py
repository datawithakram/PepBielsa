import os
from data_aggregator import aggregator
from tactical_engine import compute_tactical_summary_from_scraping
from visuals import generate_all_graphics

def main():
    match_id = 10230635
    print(f"Fetching deep data from SofaScore for match ID: {match_id} (Argentina vs France)")
    raw_data = aggregator.get_match_all_data(match_id)
    
    print("Computing tactical summary...")
    summary = compute_tactical_summary_from_scraping(raw_data)
    
    output_dir = os.path.join(os.path.dirname(__file__), "outputs", "argentina_france_2022")
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Generating graphics to {output_dir}...")
    generate_all_graphics(summary, save_dir=output_dir)
    print("Done! Real data graphics generated successfully.")

if __name__ == "__main__":
    main()
