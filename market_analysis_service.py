import logging
import statistics
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Ad, AdSearchIndex, SourceType

logger = logging.getLogger(__name__)

# --- CONFIGURATION CONSTANTS ---
LOOKBACK_WINDOW_DAYS = 180
MIN_COMPARABLES_REQUIRED = 5
BELOW_MARKET_THRESHOLD_PCT = 0.10
IQR_MULTIPLIER = 1.5
NO_DATA_ALERT_THRESHOLD_PCT = 0.40

# Sanity limits per category id (e.g. 1 = Real Estate)
# Format: { category_id: (min_price, max_price) }
PRICE_SANITY_BOUNDS = {
    1: (1000.0, 10_000_000.0), # Generic Real Estate
    2: (3000.0, 10_000_000.0), # Real estate for sale
    10301: (5000.0, 10_000_000.0), # Apartments for sale
    10302: (5000.0, 10_000_000.0), # Studios for sale
    10102: (5000.0, 10_000_000.0), # Houses for sale
    10104: (5000.0, 10_000_000.0), # Whole floors for sale
    101: (300.0, 500_000.0),       # Cars for sale
    'default': (10.0, 1_000_000_000.0)
}

def _parse_age(attrs: dict) -> Optional[float]:
    if not attrs:
        return None
    val = attrs.get("عمر البناء") or attrs.get("building_age") or attrs.get("age")
    if val is None:
        return None
    try:
        if isinstance(val, str):
            # E.g. "1-5 سنوات" -> 3, "جديد لم يسكن" -> 0, "أكثر من 20 سنة" -> 25
            if "جديد" in val: return 0.0
            if "أكثر" in val or ">" in val:
                nums = [float(s) for s in val.split() if s.isdigit()]
                return nums[0] + 5 if nums else 20.0
            nums = [float(s) for s in val.replace("-", " ").split() if s.isdigit()]
            if len(nums) == 2: return sum(nums) / 2.0
            if len(nums) == 1: return nums[0]
        return float(val)
    except Exception:
        return None

def _clean_outliers(prices: List[float]) -> List[float]:
    if len(prices) < 4:
        return prices
    prices_sorted = sorted(prices)
    q1_idx = len(prices_sorted) // 4
    q3_idx = (len(prices_sorted) * 3) // 4
    q1 = prices_sorted[q1_idx]
    q3 = prices_sorted[q3_idx]
    iqr = q3 - q1
    lower_bound = q1 - IQR_MULTIPLIER * iqr
    upper_bound = q3 + IQR_MULTIPLIER * iqr
    return [p for p in prices_sorted if lower_bound <= p <= upper_bound]

class MarketAnalysisService:
    
    @staticmethod
    def calculate_and_save(ad_id: int, db: Session) -> None:
        # Legacy entrypoint - just calls the batch job logic for one ad
        MarketAnalysisService.run_batch(db, incremental=False, dry_run=False, specific_ad_id=ad_id)

    @classmethod
    def run_batch(cls, db: Session, incremental: bool = True, dry_run: bool = False, specific_ad_id: Optional[int] = None) -> None:
        start_time = datetime.utcnow()
        logger.info(f"Starting market analysis batch job (incremental={incremental}, dry_run={dry_run}, ad_id={specific_ad_id})")
        
        query = db.query(Ad).join(AdSearchIndex, Ad.id == AdSearchIndex.ad_id).filter(
            Ad.is_published == True,
            Ad.is_paused == False,
            Ad.is_sold == False,
            Ad.is_rejected == False,
            Ad.price.isnot(None),
            Ad.source_type == SourceType.ORGANIC_USER
        )
        
        if specific_ad_id:
            query = query.filter(Ad.id == specific_ad_id)
        elif incremental:
            # Re-evaluate ads that have never been calculated or were updated since last calculation
            query = query.filter(
                (Ad.calculated_at == None) | 
                (Ad.updated_at > Ad.calculated_at)
            )
            
        ads_to_process = query.all()
        total_processed = 0
        status_counts = {"BELOW_MARKET": 0, "NOT_BELOW_MARKET": 0, "NO_DATA": 0}
        conf_counts = {"high": 0, "medium": 0, "low": 0, "no_data": 0}
        
        now = datetime.utcnow()
        lookback_date = now - timedelta(days=LOOKBACK_WINDOW_DAYS)
        
        for ad in ads_to_process:
            total_processed += 1
            idx = db.query(AdSearchIndex).filter(AdSearchIndex.ad_id == ad.id).first()
            if not idx:
                continue
                
            sanity_min, sanity_max = PRICE_SANITY_BOUNDS.get(ad.category_id, PRICE_SANITY_BOUNDS['default'])
            if not (sanity_min <= float(ad.price) <= sanity_max):
                cls._mark_no_data(ad)
                status_counts["NO_DATA"] += 1
                conf_counts["no_data"] += 1
                continue
                
            # Base comparables
            comps_query = db.query(Ad.price, AdSearchIndex.city_id, AdSearchIndex.region_id, 
                                   AdSearchIndex.floor_number, Ad.attributes, AdSearchIndex.build_area).join(
                AdSearchIndex, AdSearchIndex.ad_id == Ad.id
            ).filter(
                Ad.id != ad.id,
                Ad.is_published == True,
                Ad.is_paused == False,
                Ad.is_sold == False,
                Ad.is_rejected == False,
                Ad.category_id == ad.category_id,
                Ad.created_at >= lookback_date,
                Ad.price >= sanity_min,
                Ad.price <= sanity_max
            )
            
            if idx.property_type: comps_query = comps_query.filter(AdSearchIndex.property_type == idx.property_type)
            if idx.deal_type: comps_query = comps_query.filter(AdSearchIndex.deal_type == idx.deal_type)
            if idx.bedrooms is not None: comps_query = comps_query.filter(AdSearchIndex.bedrooms == idx.bedrooms)
            
            raw_comps = comps_query.all()
            
            t_age = _parse_age(ad.attributes)
            t_floor = float(idx.floor_number) if idx.floor_number is not None else None
            t_area = float(idx.build_area) if idx.build_area else None
            t_price = float(ad.price)
            t_rent_duration = ad.attributes.get('dynamic_data', {}).get('rent_duration') if ad.attributes and isinstance(ad.attributes, dict) else None
            
            # Helper to filter comparables
            def get_level_prices(city_match=True, reg_match=True, floor_diff=None, age_diff=None, area_pct=None):
                prices = []
                for p_val, c_city, c_reg, c_floor, c_attrs, c_area in raw_comps:
                    if city_match and c_city != idx.city_id: continue
                    if reg_match and c_reg != idx.region_id: continue
                    
                    if t_rent_duration is not None:
                        c_rent = c_attrs.get('dynamic_data', {}).get('rent_duration') if c_attrs and isinstance(c_attrs, dict) else None
                        if c_rent != t_rent_duration: continue
                    
                    if floor_diff is not None and t_floor is not None:
                        c_f = float(c_floor) if c_floor is not None else None
                        if c_f is None or abs(c_f - t_floor) > floor_diff: continue
                        
                    if age_diff is not None and t_age is not None:
                        c_a = _parse_age(c_attrs)
                        if c_a is None or abs(c_a - t_age) > age_diff: continue
                        
                    if area_pct is not None and t_area is not None:
                        c_ar = float(c_area) if c_area else None
                        if c_ar is None: continue
                        if not (t_area * (1 - area_pct) <= c_ar <= t_area * (1 + area_pct)): continue
                        
                    prices.append(float(p_val))
                return prices

            # Progressive Matching
            level_configs = [
                (1, "high", dict(city_match=True, reg_match=True, floor_diff=1, age_diff=3, area_pct=0.10)),
                (2, "medium", dict(city_match=True, reg_match=True, floor_diff=2, age_diff=7, area_pct=0.10)),
                (3, "low", dict(city_match=True, reg_match=False, floor_diff=None, age_diff=None, area_pct=0.15)),
            ]
            
            matched = False
            for lvl_num, conf, kwargs in level_configs:
                lvl_prices = get_level_prices(**kwargs)
                cleaned = _clean_outliers(lvl_prices)
                
                if len(cleaned) >= MIN_COMPARABLES_REQUIRED:
                    median_price = statistics.median(cleaned)
                    dev_pct = (t_price - median_price) / median_price
                    
                    if dev_pct <= -BELOW_MARKET_THRESHOLD_PCT:
                        ad.market_price_status = "BELOW_MARKET"
                        status_counts["BELOW_MARKET"] += 1
                    else:
                        ad.market_price_status = "NOT_BELOW_MARKET"
                        status_counts["NOT_BELOW_MARKET"] += 1
                        
                    ad.market_average_price = median_price
                    ad.deviation_pct = dev_pct
                    ad.comparables_count = len(cleaned)
                    ad.confidence_level = conf
                    ad.matching_level_used = lvl_num
                    ad.calculated_at = now
                    conf_counts[conf] += 1
                    matched = True
                    break
            
            if not matched:
                cls._mark_no_data(ad)
                ad.calculated_at = now
                status_counts["NO_DATA"] += 1
                conf_counts["no_data"] += 1

        if not dry_run and total_processed > 0:
            db.commit()
            
        exec_time = (datetime.utcnow() - start_time).total_seconds()
        
        no_data_ratio = status_counts["NO_DATA"] / total_processed if total_processed > 0 else 0
        if no_data_ratio > NO_DATA_ALERT_THRESHOLD_PCT:
            logger.warning(f"HIGH NO_DATA RATIO: {no_data_ratio*100:.1f}%")
            
        logger.info(f"Batch completed in {exec_time:.2f}s. Processed: {total_processed}. "
                    f"Statuses: {status_counts}. Confidences: {conf_counts}.")
                    
    @staticmethod
    def _mark_no_data(ad):
        ad.market_price_status = "NO_DATA"
        ad.market_average_price = None
        ad.deviation_pct = None
        ad.comparables_count = 0
        ad.confidence_level = "no_data"
        ad.matching_level_used = None
