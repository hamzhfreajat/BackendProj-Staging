from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, text
import difflib
from datetime import datetime, timedelta

from database import get_db
from models import Ad, AdSearchIndex
from schemas_duplicate import DuplicateCandidateResponse, DuplicateStatus

router = APIRouter(prefix="/api/admin/ads", tags=["Admin Duplicates"])

def hex_to_int(h):
    try:
        return int(h, 16)
    except:
        return 0

def calculate_hamming_distance(hash1: str, hash2: str) -> int:
    if not hash1 or not hash2:
        return 64 # max distance
    val1 = hex_to_int(hash1)
    val2 = hex_to_int(hash2)
    xor_val = val1 ^ val2
    return bin(xor_val).count('1')

@router.get("/{ad_id}/check-duplicates", response_model=list[DuplicateCandidateResponse])
def check_duplicates(ad_id: int, db: Session = Depends(get_db)):
    # 1. Fetch Target Ad
    target_ad = db.query(Ad).filter(Ad.id == ad_id).first()
    if not target_ad:
        raise HTTPException(status_code=404, detail="Target Ad not found")

    target_index = db.query(AdSearchIndex).filter(AdSearchIndex.ad_id == ad_id).first()
    if not target_index:
        raise HTTPException(status_code=404, detail="Target Ad Index not found")

    # 2. Phase 1: Candidate Generation
    si = AdSearchIndex
    
    # Base filter
    si = AdSearchIndex
    si_filter_date = datetime.utcnow() - timedelta(days=60)
    query = db.query(si, Ad).join(Ad, Ad.id == si.ad_id).filter(
        si.ad_id != ad_id,
        si.category_id == target_index.category_id,
        Ad.created_at >= si_filter_date
    )
    
    # City and Region matching (handle nulls safely)
    if target_index.city_id:
        query = query.filter(si.city_id == target_index.city_id)
    if target_index.region_id:
        query = query.filter(si.region_id == target_index.region_id)
        
    # Price +- 5%
    if target_index.price:
        p_min = float(target_index.price) * 0.95
        p_max = float(target_index.price) * 1.05
        query = query.filter(si.price >= p_min, si.price <= p_max)
        
    # Build Area +- 5%
    if target_index.build_area:
        b_min = float(target_index.build_area) * 0.95
        b_max = float(target_index.build_area) * 1.05
        query = query.filter(si.build_area >= b_min, si.build_area <= b_max)
        
    candidates = query.all()
    
    results = []
    
    target_search_text = (target_index.search_text or "").lower()
    
    # 3. Phase 2: Scoring Service
    for cand_index, cand_ad in candidates:
        score_breakdown = {
            "author": 0,
            "specs": 0,
            "text": 0,
            "image": 0
        }
        
        # Author Match (20 Points)
        if target_ad.user_id and target_ad.user_id == cand_ad.user_id:
            score_breakdown["author"] = 20
            
        # Hard Specs Match (30 Points)
        specs_score = 0
        total_specs_to_check = 0
        
        if target_index.bedrooms is not None:
            total_specs_to_check += 1
            if cand_index.bedrooms == target_index.bedrooms:
                specs_score += 1
                
        if target_index.bathrooms is not None:
            total_specs_to_check += 1
            if cand_index.bathrooms == target_index.bathrooms:
                specs_score += 1
                
        if target_index.floor_number is not None:
            total_specs_to_check += 1
            if cand_index.floor_number == target_index.floor_number:
                specs_score += 1
                
        if target_index.property_type is not None:
            total_specs_to_check += 1
            if cand_index.property_type == target_index.property_type:
                specs_score += 1
                
        if total_specs_to_check > 0:
            score_breakdown["specs"] = int((specs_score / total_specs_to_check) * 30)
        else:
            # If no specs exist, we can't award/deduct, maybe neutral or 0? 
            # We'll just keep it 0 as per strict evaluation, or proportionally re-weight? Let's stick to 0.
            score_breakdown["specs"] = 0
            
        # Text Similarity (25 Points)
        cand_search_text = (cand_index.search_text or "").lower()
        if target_search_text and cand_search_text:
            ratio = difflib.SequenceMatcher(None, target_search_text, cand_search_text).ratio()
            score_breakdown["text"] = int(ratio * 25)
            
        # Image Similarity (25 Points)
        if target_ad.primary_image_hash and cand_ad.primary_image_hash:
            distance = calculate_hamming_distance(target_ad.primary_image_hash, cand_ad.primary_image_hash)
            # Distance 0 => identical => 25 pts. Distance 64 => completely different => 0 pts.
            # Usually < 10 is very similar.
            if distance <= 10:
                img_score = 25 - (distance * 2) # max 25, drops rapidly
                score_breakdown["image"] = max(0, img_score)
            else:
                score_breakdown["image"] = 0
                
        total_score = sum(score_breakdown.values())
        
        if total_score >= 80:
            status = DuplicateStatus.REJECTED_DUPLICATE
        elif total_score >= 50:
            status = DuplicateStatus.FLAGGED_FOR_REVIEW
        else:
            status = DuplicateStatus.ACCEPTED
            
        results.append(DuplicateCandidateResponse(
            target_ad_id=target_ad.id,
            candidate_ad_id=cand_ad.id,
            total_score=total_score,
            score_breakdown=score_breakdown,
            status=status
        ))
        
    results.sort(key=lambda x: x.total_score, reverse=True)
    
    # Save the highest score and corresponding status to the target ad
    if results:
        highest_cand = results[0]
        target_ad.highest_duplicate_score = highest_cand.total_score
        target_ad.duplicate_status = highest_cand.status
    else:
        target_ad.highest_duplicate_score = 0
        target_ad.duplicate_status = DuplicateStatus.ACCEPTED
        
    db.commit()
    
    return results
