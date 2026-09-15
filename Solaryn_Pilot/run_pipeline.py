from pathlib import Path
import pandas as pd

from src.climate_fingerprint import compute_climate_fingerprint
from src.recommendation_engine import rank_technologies

ROOT = Path(__file__).resolve().parent

print("Solaryn research-screening runner")
print("WARNING: This script is NOT the EPC procurement engine and must not be used as a commercial recommendation.")
print("For EPC module comparison run: python -m streamlit run app/streamlit_app.py")

sites = pd.read_csv(ROOT / "data/raw/sites.csv")
tech = pd.read_csv(ROOT / "data/raw/technology_master.csv")
features = compute_climate_fingerprint(sites)

all_scores = []
for _, site in features.iterrows():
    ranking = rank_technologies(site, tech)
    ranking.insert(0, "site_id", site["site_id"])
    all_scores.append(ranking.drop(columns=["reasons", "risks"], errors="ignore"))

out = pd.concat(all_scores, ignore_index=True)
out_path = ROOT / "outputs/research_screening_scores.csv"
out_path.parent.mkdir(exist_ok=True)
out.to_csv(out_path, index=False)
print(f"Research-screening output written to {out_path}")
