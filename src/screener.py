"""
screener.py — Orchestrate multiple resume screenings.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable

from .scorer import ResumeScorer, ScoringWeights, ScoreResult


@dataclass
class ScreeningSession:
    """Results from screening multiple resumes."""
    results: List[ScoreResult] = field(default_factory=list)
    job_description: str = ""
    total_tokens: int = 0
    elapsed_seconds: float = 0.0

    @property
    def ranked(self) -> List[ScoreResult]:
        """Return results sorted by overall_score."""
        return sorted(self.results, key=lambda x: x.overall_score, reverse=True)


class ResumeScreener:
    """Screen multiple resumes against a job description."""

    def __init__(self, api_key: str, provider: str = "gemini", model: Optional[str] = None, weights: Optional[ScoringWeights] = None):
        self.scorer = ResumeScorer(api_key=api_key, provider=provider, model=model, weights=weights)

    def screen_texts(self, texts: Dict[str, str], job_description: str, progress_callback: Optional[Callable] = None) -> ScreeningSession:
        """Screen multiple resumes."""
        session = ScreeningSession(job_description=job_description)
        start_time = time.time()
        total = len(texts)

        for idx, (filename, content) in enumerate(texts.items(), 1):
            if progress_callback:
                progress_callback(idx, total, filename)
            
            result = self.scorer.score(content, job_description, filename)
            session.results.append(result)

        session.elapsed_seconds = time.time() - start_time
        return session
