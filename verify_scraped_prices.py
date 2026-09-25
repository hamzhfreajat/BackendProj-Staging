import os
import sys
import httpx
import json
import logging
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Ad, SourceType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

def verify_price(raw_description: str, price: float) -> bool:
    if not DEEPSEEK_API_KEY:
        logger.warning("No DEEPSEEK_API_KEY found, skipping AI check and returning False.")
        return False
        
    prompt = f"""You are a real estate verification AI.
Here is the original text from a Facebook real estate post:
"{raw_description}"

The extracted price in the database is: {price}

Task: Verify if this price strictly represents the total property price (or full rent amount) according to the post.
- If the price matches the main price mentioned in the text, return is_certain: true.
- If the text mentions that this price is just an installment (قسط), downpayment (دفعة أولى), or is ambiguous, return is_certain: false.
- If the text doesn't clearly mention this price, return is_certain: false.

Return ONLY a JSON object:
{{
  "is_certain": true | false,
  "reason": "short explanation"
}}
"""
    try:
        response = httpx.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}
            },
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
        result = json.loads(data['choices'][0]['message']['content'])
        logger.info(f"Verification result: {result}")
        return result.get('is_certain', False)
    except Exception as e:
        logger.error(f"Error during AI verification: {e}")
        return False

def main():
    db = SessionLocal()
    try:
        scraped_ads = db.query(Ad).filter(
            Ad.source_type == SourceType.SCRAPER_BOT,
            Ad.is_published == True,
            Ad.raw_description.isnot(None),
            Ad.price.isnot(None)
        ).all()
        
        logger.info(f"Found {len(scraped_ads)} published scraped ads to verify.")
        
        updated_count = 0
        for ad in scraped_ads:
            logger.info(f"Checking Ad #{ad.id} (Price: {ad.price})")
            is_valid = verify_price(ad.raw_description, float(ad.price))
            
            if not is_valid:
                logger.info(f"Price for Ad #{ad.id} is uncertain or wrong. Setting is_published to False.")
                ad.is_published = False
                updated_count += 1
            else:
                logger.info(f"Price for Ad #{ad.id} is confirmed.")
                
        db.commit()
        logger.info(f"Verification complete. Unpublished {updated_count} ads due to uncertain pricing.")
    finally:
        db.close()

if __name__ == '__main__':
    main()
