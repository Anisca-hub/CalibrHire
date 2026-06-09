import json
import re
import random
from dataclasses import dataclass, field, asdict
from typing import Optional, List

@dataclass
class ScoringWeights:
    """Relative importance of each scoring dimension."""
    skills: float = 0.40
    experience: float = 0.30
    education: float = 0.15
    cultural_fit: float = 0.15

@dataclass
class ScoreResult:
    """Full scoring result for a single resume."""
    filename: str = ""
    overall_score: float = 0.0
    recommendation: str = "No"
    skills_score: float = 0.0
    experience_score: float = 0.0
    education_score: float = 0.0
    cultural_fit_score: float = 0.0
    years_of_experience: float = 0.0
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    education_level: str = ""
    summary: str = ""
    justification: str = ""
    tokens_used: int = 0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

class ResumeScorer:
    """Score a resume against a job description using an LLM."""

    def __init__(self, api_key: str, provider: str = "gemini", model: str = None, weights: ScoringWeights = None):
        self.api_key = api_key
        self.provider = provider
        self.model = model or "gemini-1.5-flash"
        self.weights = weights or ScoringWeights()

    def get_recommendation_label(self, score: float) -> str:
        """Return a professional grade based on the overall score."""
        if score >= 85: return "Elite"
        if score >= 70: return "Strong"
        if score >= 50: return "Qualified"
        return "Not a Match"

    def score(self, resume_text: str, job_description: str, filename: str = "resume") -> ScoreResult:
        """Score a single resume."""
        result = ScoreResult(filename=filename)
        
        # Mock scoring for testing
        result.skills_score = random.randint(60, 95)
        result.experience_score = random.randint(50, 90)
        result.education_score = random.randint(55, 85)
        result.cultural_fit_score = random.randint(60, 80)
        result.years_of_experience = random.randint(2, 10)
        
        # Calculate weighted score
        result.overall_score = (
            result.skills_score * self.weights.skills +
            result.experience_score * self.weights.experience +
            result.education_score * self.weights.education +
            result.cultural_fit_score * self.weights.cultural_fit
        )
        
        # Assign recommendation using the new helper method
        result.recommendation = self.get_recommendation_label(result.overall_score)
            
        result.summary = f"Candidate has {result.years_of_experience} years of experience with relevant skills."
        result.justification = f"Score based on skills ({result.skills_score:.0f}), experience ({result.experience_score:.0f}), education ({result.education_score:.0f}), and fit ({result.cultural_fit_score:.0f})."
        result.matched_skills = ["Python", "SQL", "API Development"]
        result.missing_skills = ["Cloud", "Docker"]
        result.education_level = "Bachelor's Degree"
            
        return result