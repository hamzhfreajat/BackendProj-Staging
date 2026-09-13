import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from models import Ad, AdSearchIndex
import statistics

logger = logging.getLogger(__name__)

class MarketAnalysisService:
    @staticmethod
    def calculate_and_save(ad_id: int, db: Session) -> None:
        target_ad = db.query(Ad).filter(Ad.id == ad_id).first()
        if not target_ad or target_ad.price is None:
            return
            
        target_index = db.query(AdSearchIndex).filter(AdSearchIndex.ad_id == ad_id).first()
        if not target_index:
            return
            
        six_months_ago = datetime.utcnow() - timedelta(days=180)
        
        # We need the price and the attributes to filter by age
        query = db.query(Ad.price, Ad.attributes).join(
            AdSearchIndex, AdSearchIndex.ad_id == Ad.id
        ).filter(
            Ad.id != ad_id,
            Ad.category_id == target_ad.category_id,
            Ad.created_at >= six_months_ago,
            AdSearchIndex.city_id == target_index.city_id,
            AdSearchIndex.region_id == target_index.region_id,
            Ad.price.isnot(None),
            Ad.price > 10 # Filter out obvious fake low prices generically
        )
        
        # Real Estate dynamic specs
        if target_index.property_type:
            query = query.filter(AdSearchIndex.property_type == target_index.property_type)
        if target_index.deal_type:
            query = query.filter(AdSearchIndex.deal_type == target_index.deal_type)
        if target_index.bedrooms is not None:
            query = query.filter(AdSearchIndex.bedrooms == target_index.bedrooms)
        if target_index.floor_number is not None:
            query = query.filter(AdSearchIndex.floor_number == target_index.floor_number)
            
        # Area matching
        if target_index.build_area:
            b_min = float(target_index.build_area) * 0.90
            b_max = float(target_index.build_area) * 1.10
            query = query.filter(AdSearchIndex.build_area >= b_min, AdSearchIndex.build_area <= b_max)
            
        results = query.all()
        
        # In-memory filter for building age if present in target_ad
        target_attrs = target_ad.attributes or {}
        target_age = target_attrs.get("OU...O1 O'U,O(U+O'O") or target_attrs.get("building_age") or target_attrs.get("age")
        
        prices = []
        for price_val, attrs in results:
            attrs = attrs or {}
            cand_age = attrs.get("OU...O1 O'U,O(U+O'O") or attrs.get("building_age") or attrs.get("age")
            if target_age and cand_age:
                if target_age != cand_age:
                    continue # Strict age match
            prices.append(float(price_val))
        
        if len(prices) < 5:
            target_ad.market_price_status = "NO_DATA"
            target_ad.market_average_price = None
            db.commit()
            return
            
        # IQR filtering
        prices.sort()
        q1_idx = len(prices) // 4
        q3_idx = (len(prices) * 3) // 4
        q1 = prices[q1_idx]
        q3 = prices[q3_idx]
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        valid_prices = [p for p in prices if lower_bound <= p <= upper_bound]
        
        if len(valid_prices) < 5:
            target_ad.market_price_status = "NO_DATA"
            target_ad.market_average_price = None
            db.commit()
            return
            
        avg_price = statistics.mean(valid_prices)
        target_ad.market_average_price = avg_price
        
        target_price = float(target_ad.price)
        lower_threshold = avg_price * 0.90
        upper_threshold = avg_price * 1.10
        
        if target_price < lower_threshold:
            target_ad.market_price_status = "BELOW_MARKET"
        elif target_price > upper_threshold:
            target_ad.market_price_status = "ABOVE_MARKET"
        else:
            target_ad.market_price_status = "FAIR_PRICE"
            
        db.commit()
