from pydantic import BaseModel
from typing import Dict
from enum import Enum

class DuplicateStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    FLAGGED_FOR_REVIEW = "FLAGGED_FOR_REVIEW"
    REJECTED_DUPLICATE = "REJECTED_DUPLICATE"

class DuplicateCandidateResponse(BaseModel):
    target_ad_id: int
    candidate_ad_id: int
    total_score: int
    score_breakdown: Dict[str, int]
    status: DuplicateStatus
