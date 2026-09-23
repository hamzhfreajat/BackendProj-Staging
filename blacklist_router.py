from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
import auth
from database import get_db

router = APIRouter(prefix="/api/blacklist", tags=["blacklist"])

@router.get("/phones", response_model=List[schemas.BlockedPhoneNumberResponse])
def get_blocked_phones(
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
    return db.query(models.BlockedPhoneNumber).all()

@router.post("/phones", response_model=schemas.BlockedPhoneNumberResponse)
def add_blocked_phone(
    block_req: schemas.BlockedPhoneNumberCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
        
    phone = block_req.phone_number.strip()
    existing = db.query(models.BlockedPhoneNumber).filter(models.BlockedPhoneNumber.phone_number == phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Phone number is already blocked")
        
    new_block = models.BlockedPhoneNumber(phone_number=phone)
    db.add(new_block)
    
    # Also find and delete any existing ads belonging to this phone number via attributes
    # The phone_number is stored in the JSONB 'attributes' column for scraped ads,
    # or the ad might be owned by a user with this phone number.
    # We will query and delete ads where attributes->>'phone_number' == phone.
    
    from sqlalchemy import cast, String
    try:
        # Delete scraped ads where the phone is in attributes OR description
        # Leave organic ads alone!
        ads_to_delete = db.query(models.Ad).filter(
            (
                cast(models.Ad.attributes, String).ilike(f'%{phone}%') |
                models.Ad.description.ilike(f'%{phone}%') |
                models.Ad.raw_description.ilike(f'%{phone}%')
            ),
            models.Ad.source_type != models.SourceType.ORGANIC_USER
        ).all()
        
        for ad in ads_to_delete:
            db.delete(ad)
    except Exception as e:
        print(f"Failed to delete ads for blocked phone {phone}: {e}")
    
    db.commit()
    db.refresh(new_block)
    return new_block

@router.delete("/phones/{phone_number}", status_code=status.HTTP_204_NO_CONTENT)
def delete_blocked_phone(
    phone_number: str,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
        
    block_entry = db.query(models.BlockedPhoneNumber).filter(models.BlockedPhoneNumber.phone_number == phone_number).first()
    if not block_entry:
        raise HTTPException(status_code=404, detail="Phone number not found in blocklist")
        
    db.delete(block_entry)
    db.commit()
    return None
