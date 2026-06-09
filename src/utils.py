import json
import logging
import csv
from pathlib import Path
from typing import List, Dict, Any

def setup_logging(level=logging.INFO):
    """Configure basic logging."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

def format_duration(seconds: float) -> str:
    """Format seconds into human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.0f}s"

def estimate_tokens(text: str) -> int:
    """Rough token estimation (4 chars ~ 1 token)."""
    return len(text) // 4

def recommendation_color(recommendation: str) -> str:
    """Return a color hex for the recommendation."""
    colors = {
        "Strong Yes": "#10b981",
        "Yes": "#3b82f6",
        "Maybe": "#f59e0b",
        "No": "#ef4444",
    }
    return colors.get(recommendation, "#6b7280")

def save_results_csv(results: List[Dict], filepath: Path) -> None:
    """Save results to CSV."""
    if not results:
        return
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

def save_results_json(results: List[Dict], filepath: Path) -> None:
    """Save results to JSON."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

def get_status_badge(recommendation: str):
    colors = {"Elite": "green", "Strong": "blue", "Qualified": "orange", "Not a Match": "red"}
    return f'<span style="background-color:{colors.get(recommendation, "gray")}; color:white; padding:4px 8px; border-radius:4px; font-size:0.8em;">{recommendation}</span>'