import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.sql import func, or_
import redis
import json
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response

try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD", None),
        decode_responses=True
    )
except Exception:
    redis_client = None

import models
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel
import re

def escape_like(s: str) -> str:
    if not s: return ""
    return re.sub(r'([%_\\])', r'\\\1', s)

def norm_str(s):
    if not s: return s
    for a, b in [('أ', 'ا'), ('إ', 'ا'), ('آ', 'ا'), ('ة', 'ه'), ('ى', 'ي')]:
        s = s.replace(a, b)
    return s

def normalize_region_name(name):
    if not name: return name
    n = norm_str(name).strip()
    if n.startswith('ال'):
        n = n[2:].strip()
    return n

def norm_col(col):
    from sqlalchemy.sql import func
    c = func.replace(col, 'أ', 'ا')
    c = func.replace(c, 'إ', 'ا')
    c = func.replace(c, 'آ', 'ا')
    c = func.replace(c, 'ة', 'ه')
    c = func.replace(c, 'ى', 'ي')
    return c

def norm_region_col(col):
    from sqlalchemy.sql import func
    c = norm_col(col)
    return func.regexp_replace(c, '^ال', '')


import redis
import json
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response

try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD", None),
        decode_responses=True
    )
except Exception:
    redis_client = None

import models
import schemas
import auth
import notifications
from notifications import send_personal_notification
from database import engine, get_db, SessionLocal
from fb_batch_router import router as fb_batch_router
from fb_publisher_router import router as fb_publisher_router
from ai_router import router as ai_router
from search_service import SearchService
from autocomplete_service import AutocompleteService
from media_router import router as media_router
from og_router import router as og_router
from fastapi.staticfiles import StaticFiles

import uuid
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from auth import get_real_ip
from security_events import request_id_ctx, log_system_error, log_schema_validation_failure, log_bola_attempt

import os
import json
try:
    from google import genai as _genai_new
    _USE_NEW_SDK = True
except ImportError:
    import google.generativeai as genai
    _USE_NEW_SDK = False

# Rely entirely on coolify .env environment variables for API keys
if not os.getenv("GOOGLE_API_KEY"):
    print("WARNING: GOOGLE_API_KEY is not set in the environment.")

app = FastAPI(
    title="Classifieds Backend API",
    docs_url=None if os.getenv("ENV") == "production" else "/docs",
    redoc_url=None if os.getenv("ENV") == "production" else "/redoc",
    openapi_url=None if os.getenv("ENV") == "production" else "/openapi.json"
)

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from limiter import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Ensure all database tables exist (creates newly added tables like saved_ads)
models.Base.metadata.create_all(bind=engine)




from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
if _raw_origins and _raw_origins != "*":
    ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]
else:
    # Default to the specific frontend domain if not set
    ALLOWED_ORIGINS = ["https://joapp.space", "https://www.joapp.space", "http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "ngrok-skip-browser-warning", "Bypass-Tunnel-Reminder"],
)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["127.0.0.1", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"])
import time
from database import SessionLocal

@app.middleware("http")
async def api_hit_tracking_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time_ms = (time.time() - start_time) * 1000.0

    path = request.url.path
    
    endpoint_name = None
    if path == "/api/dashboard/metrics":
        endpoint_name = "Home Page"
    elif path == "/api/categories":
        if "parent_id" in request.query_params:
            endpoint_name = "Category Page"
    elif path == "/api/ads":
        if "categoryId" in request.query_params or "category_id" in request.query_params:
            endpoint_name = "Category Details"
    elif path.startswith("/api/ads/") and request.method == "GET":
        parts = path.split("/")
        if len(parts) == 4 and parts[3].isdigit():
            endpoint_name = "Ad Details"
            
    if endpoint_name:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0].strip()
        else:
            ip_address = request.client.host if request.client else "unknown"
            
        user_agent = request.headers.get("User-Agent")
        status_code = response.status_code
        query_params = str(request.query_params)
        
        user_id = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                import jwt
                from auth import SECRET_KEY, ALGORITHM
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                uid = payload.get("sub")
                if uid:
                    user_id = int(uid)
            except Exception:
                pass
                
        def save_log():
            try:
                db = SessionLocal()
                new_log = models.ApiHitLog(
                    endpoint_name=endpoint_name,
                    ip_address=ip_address,
                    response_time_ms=process_time_ms,
                    status_code=status_code,
                    user_agent=user_agent,
                    query_params=query_params,
                    user_id=user_id
                )
                db.add(new_log)
                db.commit()
                db.close()
            except Exception as e:
                print(f"Error saving API hit log: {e}")
                
        from fastapi.concurrency import run_in_threadpool
        asyncio.create_task(run_in_threadpool(save_log))

    return response

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)

@app.middleware("http")
async def security_context_middleware(request: Request, call_next):
    req_id = str(uuid.uuid4())
    request_id_ctx.set(req_id)
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response

@app.middleware("http")
async def cloudflare_edge_caching(request: Request, call_next):
    response = await call_next(request)
    
    # Only cache successful GET requests
    if request.method == "GET" and response.status_code == 200:
        path = request.url.path
        
        # Strictly avoid caching user-specific customized endpoints
        if "/my-ads" in path or "/dashboard" in path or "/me" in path:
            return response
            
        # Heavy static lookups (categories, locations) - Cache at Cloudflare Edge for 5 minutes
        if path.startswith("/api/categories") or path.startswith("/api/locations"):
            response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"
            
        # Standard feed lists (ads, ticker) - Cache for 60 seconds to squash identical concurrent requests
        elif (path.startswith("/api/ads") and "/count" not in path) or path.startswith("/api/ticker"):
            response.headers["Cache-Control"] = "public, max-age=60, s-maxage=60"
            
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    ip = get_real_ip(request)
    log_system_error(ip, request.url.path, f"Unhandled server crash: {str(exc)}")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    ip = get_real_ip(request)
    log_schema_validation_failure(ip, request.url.path, str(exc.errors()))
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

app.include_router(fb_batch_router)
app.include_router(fb_publisher_router)

from duplicate_detection_router import router as duplicate_router
from routers import users_admin_router
import wallet_router
app.include_router(users_admin_router.router)
app.include_router(duplicate_router)
app.include_router(wallet_router.router)

app.include_router(ai_router)
from smart_search_router import smart_search_router
app.include_router(smart_search_router)
app.include_router(media_router)
app.include_router(og_router)
app.include_router(auth.router)
app.include_router(notifications.router)

# from verification import router as verification_router
# app.include_router(verification_router)

from tracking_router import router as tracking_router
app.include_router(tracking_router)

from whatsapp_router import router as whatsapp_router
app.include_router(whatsapp_router)

from telemetry_router import router as telemetry_router
app.include_router(telemetry_router)
from blacklist_router import router as blacklist_router
app.include_router(blacklist_router)


# Mount the uploads directory to serve media files
import os
os.makedirs("uploads", exist_ok=True)
os.makedirs("static/icons", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/api/dashboard/metrics", response_model=schemas.UserMetrics)
def read_user_metrics(request: Request, db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    user = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            import jwt
            payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                user = db.query(models.User).filter(models.User.id == int(user_id)).first()
        except jwt.PyJWTError:
            pass

    if not user:
        return schemas.UserMetrics(id=0, user_id=0, saved_items=0, recently_viewed=0, active_ads=0)
    
    active_ads_count = db.query(models.Ad).filter(
        models.Ad.user_id == user.id,
        models.Ad.is_published == True
    ).count()

    saved_items_count = db.query(models.SavedAd).filter(
        models.SavedAd.user_id == user.id
    ).count()

    metrics = db.query(models.UserMetric).filter(models.UserMetric.user_id == user.id).first()
    if not metrics:
        metrics = models.UserMetric(user_id=user.id, saved_items=saved_items_count, recently_viewed=0, active_ads=active_ads_count)
        db.add(metrics)
        db.commit()
        db.refresh(metrics)
    else:
        needs_commit = False
        if metrics.active_ads != active_ads_count:
            metrics.active_ads = active_ads_count
            needs_commit = True
        if metrics.saved_items != saved_items_count:
            metrics.saved_items = saved_items_count
            needs_commit = True
            
        if needs_commit:
            db.commit()
            db.refresh(metrics)
            
    return metrics

from sqlalchemy.orm import selectinload

@app.get("/api/locations", response_model=List[schemas.CityModel])
def read_locations(db: Session = Depends(get_db)):
    """Fetch all cities along with their sub-regions."""
    cities = db.query(models.City).options(selectinload(models.City.regions)).all()
    return cities

@app.get("/api/locations/directorates/{governorate_id}")
def get_directorates(governorate_id: int, db: Session = Depends(get_db)):
    result = db.query(models.Directorate).filter(models.Directorate.city_id == governorate_id).all()
    return [{"id": c.id, "name_ar": c.name_ar} for c in result]

@app.get("/api/locations/villages/{directorate_id}")
def get_villages(directorate_id: int, db: Session = Depends(get_db)):
    result = db.query(models.Village).filter(models.Village.directorate_id == directorate_id).all()
    return [{"id": v.id, "name_ar": v.name_ar} for v in result]

@app.get("/api/locations/basins/{village_id}")
def get_basins(village_id: int, db: Session = Depends(get_db)):
    result = db.query(models.Basin).filter(models.Basin.village_id == village_id).all()
    return [{"id": b.id, "name_ar": b.name_ar} for b in result]

@app.get("/api/locations/neighborhoods/{basin_id}")
def get_neighborhoods(basin_id: int, db: Session = Depends(get_db)):
    result = db.query(models.NeighborhoodSector).filter(models.NeighborhoodSector.basin_id == basin_id).all()
    return [{"id": n.id, "name_ar": n.name_ar} for n in result]

@app.get("/api/categories")
def read_categories(skip: int = 0, limit: int = 20000, with_ads_only: bool = False, parent_id: str = None, location: List[str] = Query(None), db: Session = Depends(get_db)):
    skip = min(skip, 10000) # Security cap on deep pagination
    cache_key = f"categories_{skip}_{limit}_{with_ads_only}_{parent_id}_{','.join(location) if location else 'all'}"
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return Response(content=cached, media_type="application/json")
        except Exception:
            pass

    query = db.query(models.Category).options(selectinload(models.Category.linked_tags)).order_by(models.Category.order_index.asc(), models.Category.id.asc())
    
    if parent_id is not None:
        if parent_id.lower() == "null" or parent_id == "0":
            query = query.filter(models.Category.parent_id == None)
        else:
            try:
                query = query.filter(models.Category.parent_id == int(parent_id))
            except ValueError:
                pass

    categories = query.offset(skip).limit(limit).all()
    
    # FAST AD COUNT INJECTION (Recursive)
    ad_query = db.query(models.Ad.category_id, func.count(models.Ad.id)).filter(
        models.Ad.is_published == True,
        models.Ad.is_sold == False,
        models.Ad.image_url.isnot(None),
        models.Ad.image_url != '[]',
        models.Ad.image_url != ''
    )
    
    if location:
        target_loc = location[-1]
        parent_loc = location[-2] if len(location) > 1 else None
        
        if target_loc == "محافظة العاصمة": target_loc = "عمان"
        elif target_loc.startswith("محافظة "): target_loc = target_loc.replace("محافظة ", "")
        
        if parent_loc:
            if parent_loc == "محافظة العاصمة": parent_loc = "عمان"
            elif parent_loc.startswith("محافظة "): parent_loc = parent_loc.replace("محافظة ", "")
            
        target_loc_norm = norm_str(target_loc)
        parent_loc_norm = norm_str(parent_loc) if parent_loc else None
            
        filters = []
        if target_loc_norm == norm_str("أخرى") and parent_loc_norm:
            filters.append(norm_col(models.Ad.location).ilike(f"{parent_loc_norm}, أخرى%"))
            filters.append(norm_col(models.Ad.location).ilike(f"{parent_loc_norm}, other%"))
        else:
            city = db.query(models.City).filter(norm_col(models.City.name_ar) == target_loc_norm).first()
            if city:
                filters.append(norm_col(models.Ad.location).ilike(f"{escape_like(target_loc_norm)}%"))
            else:
                if parent_loc_norm:
                    filters.append(norm_col(models.Ad.location).ilike(f"{escape_like(parent_loc_norm)}, {escape_like(target_loc_norm)}%"))
                else:
                    filters.append(norm_col(models.Ad.location).ilike(f"%{escape_like(target_loc_norm)}%"))
                    
        if filters:
            ad_query = ad_query.filter(or_(*filters))
        
    ad_counts = ad_query.group_by(models.Ad.category_id).all()
        
    exact_counts = {cat_id: count for cat_id, count in ad_counts}
    
    # We must construct a FULL graph to aggregate bottom-up (even if the API result is filtered)
    all_cat_relations = db.query(models.Category.id, models.Category.parent_id).all()
    children_map = {}
    for cid, pid in all_cat_relations:
        if pid:
            children_map.setdefault(pid, []).append(cid)
            
    def get_recursive_count(cid):
        total = exact_counts.get(cid, 0)
        for child_id in children_map.get(cid, []):
            total += get_recursive_count(child_id)
        return total

    counts_map = {c.id: get_recursive_count(c.id) for c in categories}
    
    if with_ads_only:
        # Pre-calculate active categories and tags using hyper-efficient mass queries
        all_cat_ids = [c.id for c in categories]
        
        # 1. Find all published ads belonging to these categories
        all_ads = db.query(models.Ad).filter(
            models.Ad.category_id.in_(all_cat_ids),
            models.Ad.is_published == True,
            models.Ad.is_sold == False,
            models.Ad.image_url.isnot(None),
            models.Ad.image_url != '[]',
            models.Ad.image_url != ''
        ).all()
        
        active_cat_ids = set([ad.category_id for ad in all_ads])
        
        # Determine parent retention - if a child is active, the ENTIRE ancestral chain must be kept
        parent_map = {cat.id: cat.parent_id for cat in categories}
        retained_cat_ids = set()
        for active_id in active_cat_ids:
            curr_id = active_id
            while curr_id is not None:
                retained_cat_ids.add(curr_id)
                curr_id = parent_map.get(curr_id)
        
        # 2. Extract active tags efficiently
        active_tag_ids = set()
        for ad in all_ads:
            for t in ad.linked_tags:
                active_tag_ids.add(t.id)

        # 3. Build the final filtered response from memory loops instead of sequential IO queries
        filtered = []
        for cat in categories:
            if cat.id not in retained_cat_ids:
                continue
                    
            cat_dict = {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "icon_name": cat.icon_name,
                "color_hex": cat.color_hex,
                "background_url": cat.background_url,
                "tag": cat.tag,
                "slugs": cat.slugs,
                "parent_id": cat.parent_id,
                "order_index": cat.order_index,
                "ads_count": counts_map.get(cat.id, 0),
                "linked_tags": [t for t in getattr(cat, 'linked_tags', []) if t.id in active_tag_ids]
            }
            filtered.append(cat_dict)
        
        if redis_client:
            try:
                redis_client.setex(cache_key, 300, json.dumps(jsonable_encoder(filtered)))
            except Exception:
                pass
        return filtered
        
    for cat in categories:
        cat.ads_count = counts_map.get(cat.id, 0)
        
    if redis_client:
        try:
            redis_client.setex(cache_key, 300, json.dumps(jsonable_encoder(categories)))
        except Exception:
            pass
            
    return categories

@app.post("/api/categories", response_model=schemas.Category)
def create_category(
    category: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
    category_data = category.model_dump(exclude={"linked_tags"})
    db_category = models.Category(**category_data)
    
    # Process Tags
    if category.linked_tags:
        for tag_name in category.linked_tags:
            tag = db.query(models.Tag).filter(models.Tag.name == tag_name).first()
            if not tag:
                tag = models.Tag(name=tag_name)
                db.add(tag)
            db_category.linked_tags.append(tag)
            
    # Assign it as the last item automatically
    max_index = db.query(func.max(models.Category.order_index)).scalar() or 0
    db_category.order_index = max_index + 1

    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@app.put("/api/categories/reorder", response_model=dict)
def reorder_categories(
    reorder_data: List[schemas.CategoryReorder],
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
    # Bulk update method to set correct list positions efficiently
    mappings = [{"id": item.id, "order_index": item.order_index} for item in reorder_data]
    if mappings:
        db.bulk_update_mappings(models.Category, mappings)
        db.commit()
    return {"status": "success", "message": f"Successfully reordered {len(mappings)} categories"}

@app.put("/api/categories/{category_id}", response_model=schemas.Category)
def update_category(
    category_id: int,
    category_update: schemas.CategoryUpdate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
    db_category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")
        
    update_data = category_update.model_dump(exclude_unset=True, exclude={"linked_tags"})
    for key, value in update_data.items():
        setattr(db_category, key, value)
        
    # Process Tags update if provided
    if category_update.linked_tags is not None:
        db_category.linked_tags.clear() # Reset associations
        for tag_name in category_update.linked_tags:
            tag = db.query(models.Tag).filter(models.Tag.name == tag_name).first()
            if not tag:
                tag = models.Tag(name=tag_name)
                db.add(tag)
            db_category.linked_tags.append(tag)
            
    db.commit()
    db.refresh(db_category)
    return db_category

@app.delete("/api/categories/{category_id}", response_model=dict)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
    db_category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")
        
    db.delete(db_category)
    db.commit()
    return {"status": "success", "message": "Category deleted successfully"}

# ============================================================
# ADMIN-ONLY: Category Management
# All mutation endpoints below require admin privileges
# ============================================================

# ============================================================
# MY ADS / SELLER DASHBOARD
# ============================================================

from datetime import datetime, timezone

def _compute_ad_status(ad: models.Ad) -> str:
    if ad.is_sold: return "Sold"
    if ad.is_rejected: return "Rejected"
    if ad.is_paused: return "Paused"
    if not ad.is_published: return "Uncompleted"
    if ad.expires_at and ad.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc): 
        return "Expired"
    return "Active"

def _compute_performance(ad: models.Ad) -> dict:
    score = min(100, (ad.views * 0.1) + (ad.favorites_count * 2) + (ad.chats_count * 5))
    suggested = None
    if score < 20 and ad.views > 50:
        suggested = "Price might be slightly high."
    elif len(image_urls) < 0:
        suggested = "Add more photos to increase trust."
    return {"score": int(score), "action": suggested}

@app.get("/api/my-ads/dashboard", response_model=schemas.MyAdsDashboardSummary)
def get_my_ads_dashboard(
    current_user: models.User = Depends(auth.get_current_user), 
    db: Session = Depends(get_db)
):
    ads = db.query(models.Ad).filter(models.Ad.user_id == current_user.id).all()
    
    total = len(ads)
    active = 0
    expired = 0
    pending = 0
    sold = 0
    paused = 0
    boosted = 0
    
    views = 0
    chats = 0
    favs = 0
    
    for ad in ads:
        st = _compute_ad_status(ad)
        if st == "Active": active += 1
        elif st == "Expired": expired += 1
        elif st == "Uncompleted": pending += 1
        elif st == "Sold": sold += 1
        elif st == "Paused": paused += 1
        
        if ad.is_boosted: boosted += 1
        
        views += getattr(ad, 'views', 0) or 0
        chats += getattr(ad, 'chats_count', 0) or 0
        favs += getattr(ad, 'favorites_count', 0) or 0
        
    return schemas.MyAdsDashboardSummary(
        totalAds=total,
        activeAds=active,
        expiredAds=expired,
        pendingAds=pending,
        soldAds=sold,
        pausedAds=paused,
        boostedAds=boosted,
        totalViews=views,
        totalChats=chats,
        totalFavorites=favs
    )

@app.get("/api/my-ads", response_model=List[schemas.MyAdResponse])
def read_my_ads(
    status: str = "All",
    search: str = None,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.Ad).filter(models.Ad.user_id == current_user.id)
    
    if search:
        query = query.filter(models.Ad.title.ilike(f"%{escape_like(search)}%"))
        
    ads = query.order_by(models.Ad.created_at.desc()).all()
    
    response_list = []
    for ad in ads:
        computed_status = _compute_ad_status(ad)
        if status != "All" and computed_status != status:
            continue
            
        perf = _compute_performance(ad)
        
        ad_resp = schemas.MyAdResponse.model_validate(ad)
        ad_resp.status = computed_status
        ad_resp.performance_score = perf["score"]
        ad_resp.suggested_action = perf["action"]
        response_list.append(ad_resp)
        
    response_list.sort(key=lambda x: x.created_at.timestamp(), reverse=True)
    return response_list

@app.post("/api/my-ads/bulk-action", response_model=dict)
def perform_bulk_action(
    req: schemas.BulkActionRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    if len(req.ad_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 items allowed per bulk action.")

    ads = db.query(models.Ad).filter(models.Ad.id.in_(req.ad_ids), models.Ad.user_id == current_user.id).all()
    
    for ad in ads:
        if req.action == "delete":
            db.query(models.AdRealEstateDetail).filter(models.AdRealEstateDetail.ad_id == ad.id).delete()
            db.query(models.AdSearchIndex).filter(models.AdSearchIndex.ad_id == ad.id).delete()
            db.query(models.SavedAd).filter(models.SavedAd.ad_id == ad.id).delete()
            db.query(models.AdReport).filter(models.AdReport.ad_id == ad.id).delete()
            db.query(models.AdClickTracking).filter(models.AdClickTracking.ad_id == ad.id).delete()
            db.delete(ad)
        elif req.action == "pause":
            ad.is_paused = True
        elif req.action == "resume":
            ad.is_paused = False
        elif req.action == "sold":
            ad.is_sold = True
            ad.last_republished_at = func.now()
            ad.republish_notification_sent = False
        elif req.action == "renew":
            ad.is_paused = False
            ad.is_sold = False
            ad.is_published = True
        elif req.action == "republish":
            ad.is_paused = False
            ad.is_sold = False
            ad.is_published = True
            ad.last_republished_at = func.now()
            ad.republish_notification_sent = False
            ad.created_at = func.now()
            ad.updated_at = func.now()
            
    db.commit()
    return {"status": "success"}

def get_optional_user(request: Request, db: Session = Depends(get_db)):
    token = request.headers.get("Authorization")
    if not token: return None
    try:
        scheme, token = token.split()
        if scheme.lower() != "bearer": return None
        import jwt
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        user_id = payload.get("sub")
        if user_id:
            return db.query(models.User).filter(models.User.id == int(user_id)).first()
    except Exception:
        return None
    return None

@app.post("/api/ads/{ad_id}/save")
def toggle_save_ad(ad_id: int, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
        
    saved = db.query(models.SavedAd).filter(models.SavedAd.user_id == current_user.id, models.SavedAd.ad_id == ad_id).first()
    metrics = db.query(models.UserMetric).filter(models.UserMetric.user_id == current_user.id).first()
    
    if saved:
        db.delete(saved)
        if metrics and metrics.saved_items > 0:
            metrics.saved_items -= 1
        ad.favorites_count = max(0, (ad.favorites_count or 0) - 1)
        is_saved = False
    else:
        new_save = models.SavedAd(user_id=current_user.id, ad_id=ad_id)
        db.add(new_save)
        if metrics:
            metrics.saved_items += 1
        else:
            new_metric = models.UserMetric(user_id=current_user.id, saved_items=1)
            db.add(new_metric)
        ad.favorites_count = (ad.favorites_count or 0) + 1
        is_saved = True
        
    db.commit()
    return {"status": "success", "is_saved": is_saved}

@app.get("/api/users/me/saved-ads", response_model=List[schemas.Ad])
def get_saved_ads(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    saved_ads_records = db.query(models.SavedAd).filter(models.SavedAd.user_id == current_user.id).order_by(models.SavedAd.created_at.desc()).all()
    ad_ids = [r.ad_id for r in saved_ads_records]
    
    if not ad_ids:
        return []
        
    ads = db.query(models.Ad).filter(models.Ad.id.in_(ad_ids)).all()
    ads_dict = {ad.id: ad for ad in ads}
    sorted_ads = [ads_dict[ad_id] for ad_id in ad_ids if ad_id in ads_dict]
    
    for ad in sorted_ads:
        ad.is_saved = True
        
    return sorted_ads


# ============================================================
# SEARCH & AUTOCOMPLETE
# ============================================================

from sqlalchemy.sql.expression import literal



SEARCH_SYNONYMS = {
    "سياره": ["سياره", "سيارات", "مركبه", "عربيه"],
    "سيارات": ["سيارات", "سياره", "مركبات", "عربيات"],
    "شقه": ["شقه", "شقق", "استوديو", "ستوديو", "سكن", "شقة"],
    "شقق": ["شقق", "شقه", "استوديوهات", "ستوديوهات", "سكنات", "شقة"],
    "بيت": ["بيت", "بيوت", "منزل", "فيلا", "فيلات", "فلل", "منازل"],
    "بيوت": ["بيوت", "بيت", "منازل", "فلل", "فيلا", "فيلات", "منزل"],
    "فيلا": ["فيلا", "فيلات", "فلل", "بيت", "بيوت", "منزل"],
    "فيلات": ["فيلات", "فيلا", "فلل", "بيت", "بيوت", "منازل"],
    "فلل": ["فلل", "فيلا", "فيلات", "بيوت", "بيت", "منازل"],
    "محل": ["محل", "محلات", "دكان", "معرض"],
    "مخزن": ["مخزن", "مخازن", "مستودع", "مستودعات"],
    "مكتب": ["مكتب", "مكاتب", "شركه", "شركات"],
    "مزرعه": ["مزرعه", "مزرعة", "مزارع"],
    "جوال": ["جوال", "جوالات", "موبايل", "تلفون", "هاتف"],
    "جوالات": ["جوالات", "جوال", "موبايلات", "تلفونات", "هواتف"],
    "وظايف": ["وظايف", "عمل", "شغل", "توظيف", "وظيفه"],
    "وظيفه": ["وظيفه", "وظايف", "عمل", "شغل", "توظيف"],
    "بنات": ["بنات", "اناث", "بنت", "انثي"],
    "شباب": ["شباب", "ذكور", "شاب", "ذكر"]
}

def expand_term_with_synonyms(term):
    norm = norm_str(term)
    if norm in SEARCH_SYNONYMS:
        return SEARCH_SYNONYMS[norm]
    for k, v in SEARCH_SYNONYMS.items():
        if norm in v:
            return v
    return [norm]

LOCATIONS_CACHE = None

def parse_smart_search_query(q: str, db: Session):
    norm_q = norm_str(q)
    inferred_cat_id = None
    inferred_cat_name = None
    inferred_loc = None
    inferred_tags = []
    
    raw_search_terms = set(norm_q.split())
    search_terms = set()
    for t in raw_search_terms:
        search_terms.add(t)
        search_terms.update(expand_term_with_synonyms(t))
        if t == 'استوديوهات': search_terms.add('ستوديوهات')
        if t == 'ستوديوهات': search_terms.add('استوديوهات')
    
    remaining_terms = set(norm_q.split())
    expanded_remaining = set(remaining_terms)
    for term in remaining_terms:
        expanded_remaining.update(expand_term_with_synonyms(term))
    
    # 1. Direct Category Match
    all_cats = db.query(models.Category).all()
    cat_matches = []
    for cat in all_cats:
        cat_norm = norm_str(cat.name)
        cat_terms = set(cat_norm.split())
        if cat_terms and cat_terms.issubset(expanded_remaining):
            priority = 1 if cat_norm in norm_q else 0
            cat_matches.append((cat.id, len(cat_terms), cat.name, priority, cat_terms))
            
    if cat_matches:
        cat_matches.sort(key=lambda x: (x[3], x[1], x[0]), reverse=True)
        inferred_cat_id = cat_matches[0][0]
        inferred_cat_name = cat_matches[0][2]
        
        words_to_remove = set()
        for w in remaining_terms:
            w_syns = expand_term_with_synonyms(w)
            if any(syn in cat_matches[0][4] for syn in [w] + w_syns):
                words_to_remove.add(w)
        remaining_terms -= words_to_remove
    else:
        # 2. Synonym Category Match
        for k, synonyms in SEARCH_SYNONYMS.items():
            for syn in synonyms:
                if syn in remaining_terms:
                    synonym_match = db.query(models.Category).filter(models.Category.name.ilike(f"%{k}%")).order_by(func.length(models.Category.name)).first()
                    if synonym_match:
                        inferred_cat_id = synonym_match.id
                        inferred_cat_name = synonym_match.name
                        remaining_terms.discard(syn)
                        break
            if inferred_cat_id:
                break
        
    import re
    
    # Extract Price
    price_match = re.search(r'(?:بسعر|سعر|لا يتجاوز|اقل من|بحدود)\s*(\d+)\s*(ألف|الف|000)?(?!\s*متر|\s*م\b|\s*m\b)', q)
    if not price_match:
        price_match = re.search(r'(\d+)\s*(ألف|الف)(?!\s*متر|\s*م\b|\s*m\b)', q)
    if price_match:
        base_price = int(price_match.group(1))
        if price_match.lastgroup and price_match.group(price_match.lastindex) in ["ألف", "الف"]:
            base_price *= 1000
        elif price_match.group(0).endswith("ألف") or price_match.group(0).endswith("الف"):
             base_price *= 1000
        inferred_tags.append(f"max_price:{base_price}")
        for word in price_match.group(0).split():
            remaining_terms.discard(word)
            
    # Extract Area
    area_match = re.search(r'(?:مساحة|مساحتها|بمساحة)?\s*(\d+)\s*(?:متر|م\b|m\b)', q)
    if area_match:
        remaining_terms.add(area_match.group(1))
        for word in area_match.group(0).split():
            if word != area_match.group(1):
                remaining_terms.discard(word)
                
    # Extract Bedrooms
    bed_match = re.search(r'(\d+)\s*(?:نوم|غرف)', q)
    if bed_match:
        inferred_tags.append(f"bedrooms:{bed_match.group(1)}")
        for w in bed_match.group(0).split():
            remaining_terms.discard(w)
    elif "غرفتين" in remaining_terms:
        inferred_tags.append("bedrooms:2")
        remaining_terms.discard("غرفتين")
        if "وصاله" in remaining_terms: remaining_terms.discard("وصاله")
        if "وصالة" in remaining_terms: remaining_terms.discard("وصالة")
    
    # Noise Reduction (using normalized words)
    noise_words = {"في", "مع", "من", "او", "لا", "الى", "لل", "على", "عن", "ب", "ل", "و", "ف", "ك"}
    remaining_terms -= noise_words
    
    # Extract Location using dynamic Cities and Regions from DB
    global LOCATIONS_CACHE
    if LOCATIONS_CACHE is None:
        cities = [c[0] for c in db.query(models.City.name_ar).all()]
        regions = [r[0] for r in db.query(models.Region.name_ar).all()]
        locs = list(set(cities + regions))
        locs.sort(key=len, reverse=True)
        LOCATIONS_CACHE = locs
        
    for loc in LOCATIONS_CACHE:
        loc_words = norm_str(loc).split()
        matched_words = set()
        match = True
        for lw in loc_words:
            found_term = None
            for term in remaining_terms:
                if term == lw:
                    found_term = term
                    break
                if term.endswith(lw) and len(term) <= len(lw) + 2 and term[:-len(lw)] in ['ب', 'ل', 'و', 'ف', 'كال']:
                    found_term = term
                    break
                if lw.startswith('ال') and term == f"لل{lw[2:]}":
                    found_term = term
                    break
            if found_term:
                matched_words.add(found_term)
            else:
                match = False
                break
        
        if match:
            inferred_loc = loc
            remaining_terms -= matched_words
            break
            
    # Check multi-word quick tags before single-word
    multi_quick_tags = {
        "غير مفروشه": "furnished:غير مفروشة", 
        "طابق ارضي": "floor:الطابق الأرضي",
        "شبه ارضي": "floor:طابق شبه أرضي",
        "طابق اول": "floor:1",
        "طابق ثاني": "floor:2",
        "طابق ثالث": "floor:3",
        "طابق رابع": "floor:4",
        "طابق خامس": "floor:5",
        "طابق اخير": "floor:الطابق الأخير",
        "تحت الانشاء": "building_age:تحت الإنشاء",
        "ايجار يومي": "rent_duration:يومي",
        "ايجار شهري": "rent_duration:شهري",
        "ايجار سنوي": "rent_duration:سنوي",
        "للايجار اليومي": "rent_duration:يومي",
        "للايجار الشهري": "rent_duration:شهري",
        "للايجار السنوي": "rent_duration:سنوي",
        "بدون عموله": "seller_type:المالك",
        "بدون وسيط": "seller_type:المالك",
        "طاقه شمسيه": "main_features:طاقة شمسية",
        "تدفئه مركزيه": "main_features:تدفئة",
        "تحت البلاط": "main_features:تدفئة",
        "بئر ماء": "main_features:بئر ماء",
        "مطبخ راكب": "main_features:مطبخ راكب",
        "غير مفروش": "furnished:غير مفروشة"
    }
    for k, v in multi_quick_tags.items():
        tag_words = set(k.split())
        if tag_words.issubset(remaining_terms):
            inferred_tags.append(v)
            remaining_terms -= tag_words
                
    # Check single-word quick tags
    single_quick_tags = {
        "مفروشه": "furnished:مفروشة",
        "مفروش": "furnished:مفروشة",
        "بالتقسيط": "installment_possible:نعم",
        "تقسيط": "installment_possible:نعم",
        "جديده": "building_age:جديد لم يسكن",
        "ارضيه": "floor:الطابق الأرضي",
        "مسبح": "main_features:مسبح",
        "ومسبح": "main_features:مسبح",
        "تكييف": "main_features:تكييف",
        "مصعد": "main_features:مصعد",
        "كراج": "main_features:كراج",
        "انترنت": "main_features:إنترنت",
        "استوديو": "bedrooms:0",
        "استوديوهات": "bedrooms:0"
    }
    for k, v in single_quick_tags.items():
        if k in remaining_terms:
            inferred_tags.append(v)
            remaining_terms.discard(k)
            
    remaining_search = " ".join(remaining_terms) if remaining_terms else None
    
    return inferred_cat_id, inferred_cat_name, inferred_loc, inferred_tags, remaining_search

@app.get("/api/search/trending")
def get_trending_searches(db: Session = Depends(get_db)):
    """Returns top popular searches and brands."""
    tags = db.query(models.Tag.name, func.count(models.ad_tags.c.ad_id)) \
             .join(models.ad_tags) \
             .group_by(models.Tag.id) \
             .order_by(func.count(models.ad_tags.c.ad_id).desc()) \
             .limit(10).all()
    
    trending = []
    seen = set()
    for tag in tags:
        name = tag[0].split(":", 1)[-1].replace("_", " ")
        if name not in seen:
            seen.add(name)
            trending.append({"text": name, "raw_value": tag[0]})
            
    if not trending:
        return []
        
    return trending

@app.get("/api/search/autocomplete")
def search_autocomplete(q: str, db: Session = Depends(get_db)):
    """
    Intelligent Arabic-first autocomplete engine.
    Uses AutocompleteService to return structured JSON with intent and grouped suggestions.
    """
    try:
        from autocomplete_service import AutocompleteService
        from models import SearchQueryLog
        
        return AutocompleteService.generate_suggestions(db, q)
    except Exception as e:
        print(f"Autocomplete Error: {e}")
        return {
            "query": q,
            "normalized_query": q,
            "intent": {
                "deal_type": "UNKNOWN",
                "property_type": "UNKNOWN",
                "location": None,
                "price_intent": "unknown"
            },
            "groups": []
        }

@app.get("/api/admin/search_logs")
def get_search_logs(
    limit: int = 100, 
    results_count: int = Query(None, description="Filter by exact results count"),
    current_admin: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin endpoint to fetch recent raw search queries."""
    from models import SearchQueryLog
    query = db.query(SearchQueryLog)
    
    if results_count is not None:
        query = query.filter(SearchQueryLog.results_count == results_count)
        
    logs = query.order_by(SearchQueryLog.created_at.desc()).limit(limit).all()
    return [{
        "id": l.id, 
        "query_text": l.query_text, 
        "results_count": l.results_count, 
        "category_name": l.category_name,
        "extracted_tags": l.extracted_tags,
        "created_at": l.created_at.isoformat(),
        "user": {"id": l.user.id, "name": l.user.full_name or l.user.username or "Unknown", "email": l.user.email} if l.user else None
    } for l in logs]

@app.get("/api/ads", response_model=List[schemas.Ad], dependencies=[Depends(auth.get_rate_limiter(60, 60))])
def read_ads(
    skip: int = 0, 
    limit: int = 100, 
    category_id: int = None, 
    section: str = None, 
    search: str = None,
    original_search: str = None,
    location: List[str] = Query(None),
    min_price: float = None,
    max_price: float = None,
    is_hot: bool = None,
    is_published: bool = None,
    source_type: str = None,
    user_id: int = None,
    sort_by: str = None,
    tags: List[str] = Query(None),
    user_lat: float = None,
    user_lng: float = None,
    only_others: bool = False,
    location_search: str = None,
    phone: str = None,
    current_user: models.User = Depends(get_optional_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    limit = min(limit, 100) # Security cap on pagination
    skip = min(skip, 10000) # Security cap on deep pagination
    
    if location and len(location) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 locations allowed per search.")
    if tags and len(tags) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 tags allowed per search.")
        
    query = db.query(models.Ad).outerjoin(models.User, models.Ad.user_id == models.User.id)
    
    if location_search:
        query = query.filter(norm_col(models.Ad.location).ilike(f"%{norm_str(location_search).replace('،', ',')}%"))
    
    if phone:
        from sqlalchemy import cast, String
        query = query.filter(or_(
            models.User.phone.ilike(f"%{phone}%"), 
            models.User.mobile_number.ilike(f"%{phone}%"),
            cast(models.Ad.attributes, String).ilike(f"%{phone}%"),
            models.Ad.description.ilike(f"%{phone}%"),
            models.Ad.raw_description.ilike(f"%{phone}%")
        ))

    
    if user_id is not None:
        query = query.filter(models.Ad.user_id == user_id)
    from sqlalchemy.sql.expression import case
    
    # Calculate effective CPC bid (only counts if user has enough balance)
    effective_bid = case(
        ((models.User.wallet_balance >= models.Ad.cpc_bid) & (models.Ad.cpc_bid > 0), models.Ad.cpc_bid),
        else_=0
    )
    
    ignore_location = False
    if search:
        try:
            from search_parser import QueryParserService
            parsed = QueryParserService.parse(search)
            if parsed.location:
                ignore_location = True
        except:
            pass
    log_query = original_search if original_search else search
    if search:
        ranked_ad_ids = SearchService.search_properties(db, search, limit=1000)
        
        # Log the search query and results count in background
        if background_tasks and log_query and log_query.strip():
            user_id_val = current_user.id if hasattr(current_user, 'id') else None
            background_tasks.add_task(log_search_query_task, log_query, len(ranked_ad_ids), user_id_val, category_id, tags)

        if not ranked_ad_ids:
            return []
            
        query = query.filter(models.Ad.id.in_(ranked_ad_ids))
        
        # Preserve relevance ranking from SearchService
        order_cases = {ad_id: index for index, ad_id in enumerate(ranked_ad_ids)}
        whens = [(models.Ad.id == ad_id, index) for ad_id, index in order_cases.items()]
        
        if whens:
            query = query.order_by(effective_bid.desc(), case(*whens))
    elif background_tasks and log_query and log_query.strip():
        user_id_val = current_user.id if hasattr(current_user, 'id') else None
        total_results = query.count()
        background_tasks.add_task(log_search_query_task, log_query, total_results, user_id_val, category_id, tags)
        
    if location and not ignore_location:
        parent_loc = None
        target_locs = []
        
        first_loc = location[0]
        if first_loc == "محافظة العاصمة": first_loc = "عمان"
        elif first_loc.startswith("محافظة "): first_loc = first_loc.replace("محافظة ", "")
        
        target_loc_norm = norm_str(first_loc)
        city = db.query(models.City).filter(norm_col(models.City.name_ar) == target_loc_norm).first()
        if city:
            parent_loc = target_loc_norm
            target_locs = location[1:]
        else:
            target_locs = location
            
        filters = []
        if parent_loc and not target_locs:
            filters.append(norm_col(models.Ad.location).ilike(f"{parent_loc}%"))
        elif parent_loc and target_locs:
            for t_loc in target_locs:
                if t_loc == "محافظة العاصمة": t_loc = "عمان"
                elif t_loc.startswith("محافظة "): t_loc = t_loc.replace("محافظة ", "")
                t_loc_norm = norm_str(t_loc)
                
                if t_loc_norm == norm_str("أخرى"):
                    filters.append(norm_col(models.Ad.location).ilike(f"{parent_loc}, أخرى%"))
                    filters.append(norm_col(models.Ad.location).ilike(f"{parent_loc}, other%"))
                else:
                    if t_loc_norm.startswith("ال"):
                        filters.append(norm_col(models.Ad.location).ilike(f"{parent_loc}, {t_loc_norm}%"))
                        filters.append(norm_col(models.Ad.location).ilike(f"{parent_loc}, {t_loc_norm[2:]}%"))
                    else:
                        filters.append(norm_col(models.Ad.location).ilike(f"{parent_loc}, {t_loc_norm}%"))
                        filters.append(norm_col(models.Ad.location).ilike(f"{parent_loc}, ال{t_loc_norm}%"))
        else:
            for t_loc in target_locs:
                if t_loc == "محافظة العاصمة": t_loc = "عمان"
                elif t_loc.startswith("محافظة "): t_loc = t_loc.replace("محافظة ", "")
                t_loc_norm = norm_str(t_loc)
                
                if t_loc_norm == norm_str("أخرى"):
                    filters.append(norm_col(models.Ad.location).ilike(f"%أخرى%"))
                    filters.append(norm_col(models.Ad.location).ilike(f"%other%"))
                else:
                    if t_loc_norm.startswith("ال"):
                        filters.append(norm_col(models.Ad.location).ilike(f"%{t_loc_norm}%"))
                        filters.append(norm_col(models.Ad.location).ilike(f"%{t_loc_norm[2:]}%"))
                    else:
                        filters.append(norm_col(models.Ad.location).ilike(f"%{t_loc_norm}%"))
                        filters.append(norm_col(models.Ad.location).ilike(f"%ال{t_loc_norm}%"))
                    
        if filters:
            query = query.filter(or_(*filters))
            
    if only_others:
        query = query.filter(or_(
            models.Ad.location.ilike("%أخرى%"),
            models.Ad.location.ilike("%اخرى%"),
            models.Ad.location.ilike("%other%")
        ))
        
    if min_price is not None:
        query = query.filter(models.Ad.price >= min_price)
        
    if max_price is not None:
        query = query.filter(models.Ad.price <= max_price)
        
    if is_hot is not None:
        query = query.filter(models.Ad.is_hot == is_hot)
        
    if is_published is not None:
        query = query.filter(models.Ad.is_published == is_published)
    else:
        query = query.filter(models.Ad.is_published == True, models.Ad.is_sold == False)
        
    # Filter out ads without images on the home page (general feed)
    if not search and user_id is None:
        query = query.filter(models.Ad.image_url.isnot(None))
        query = query.filter(models.Ad.image_url != '[]')
        query = query.filter(models.Ad.image_url != '')
        
    if source_type:
        query = query.filter(models.Ad.source_type == source_type)
        
    if tags:
        from sqlalchemy import Integer
        from collections import defaultdict
        
        grouped_tags = defaultdict(list)
        generic_tags = []
        for t in tags:
            if ":" in t:
                prefix, val = t.split(":", 1)
                grouped_tags[prefix].append(val)
            else:
                generic_tags.append(t)
                
        for prefix, values in grouped_tags.items():
            conds = []
            if prefix == "max_price":
                for val in values:
                    query = query.filter(models.Ad.price <= float(val))
                continue
            elif prefix == "min_price":
                for val in values:
                    query = query.filter(models.Ad.price >= float(val))
                continue
            elif prefix == "min_area":
                from sqlalchemy import func
                for val in values:
                    try:
                        v = int(val)
                        numeric_area = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['area'].astext, '[^0-9]', '', 'g'), '')
                        conds.append(numeric_area.cast(Integer) >= v)
                        numeric_barea = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['building_area'].astext, '[^0-9]', '', 'g'), '')
                        conds.append(numeric_barea.cast(Integer) >= v)
                        numeric_larea = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['land_area'].astext, '[^0-9]', '', 'g'), '')
                        conds.append(numeric_larea.cast(Integer) >= v)
                        numeric_area_top = func.nullif(func.regexp_replace(models.Ad.attributes['area'].astext, '[^0-9]', '', 'g'), '')
                        conds.append(numeric_area_top.cast(Integer) >= v)
                    except: pass
            elif prefix == "max_area":
                from sqlalchemy import func
                for val in values:
                    try:
                        v = int(val)
                        numeric_area = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['area'].astext, '[^0-9]', '', 'g'), '')
                        conds.append(numeric_area.cast(Integer) <= v)
                        numeric_barea = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['building_area'].astext, '[^0-9]', '', 'g'), '')
                        conds.append(numeric_barea.cast(Integer) <= v)
                        numeric_larea = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['land_area'].astext, '[^0-9]', '', 'g'), '')
                        conds.append(numeric_larea.cast(Integer) <= v)
                        numeric_area_top = func.nullif(func.regexp_replace(models.Ad.attributes['area'].astext, '[^0-9]', '', 'g'), '')
                        conds.append(numeric_area_top.cast(Integer) <= v)
                    except: pass
            elif prefix == "area":
                for val in values:
                    conds.append(models.Ad.attributes['area'].astext.ilike(f"%{val}%"))
                    conds.append(models.Ad.attributes['dynamic_data']['area'].astext.ilike(f"%{val}%"))
                    conds.append(models.Ad.attributes['dynamic_data']['building_area'].astext.ilike(f"%{val}%"))
                    conds.append(models.Ad.attributes['dynamic_data']['land_area'].astext.ilike(f"%{val}%"))
            elif prefix == "bedrooms":
                for val in values:
                    if val == '+6':
                        conds.append(models.Ad.attributes['rooms'].astext == '+6')
                        conds.append(models.Ad.attributes['dynamic_data']['bedrooms'].astext.ilike('%6%'))
                        conds.append(models.Ad.attributes['dynamic_data']['bedrooms'].astext.ilike('%7%'))
                        conds.append(models.Ad.attributes['dynamic_data']['rooms'].astext.ilike('%6%'))
                        conds.append(models.Ad.attributes['dynamic_data']['rooms'].astext.ilike('%7%'))
                    elif val == 'ستوديو':
                        conds.append(models.Ad.attributes['rooms'].astext == '0')
                        conds.append(models.Ad.attributes['rooms'].astext == 'ستوديو')
                        conds.append(models.Ad.attributes['dynamic_data']['bedrooms'].astext.ilike('%ستوديو%'))
                        conds.append(models.Ad.attributes['dynamic_data']['bedrooms'].astext.ilike('%0%'))
                        conds.append(models.Ad.attributes['dynamic_data']['rooms'].astext.ilike('%ستوديو%'))
                        conds.append(models.Ad.attributes['dynamic_data']['rooms'].astext.ilike('%0%'))
                    else:
                        conds.append(models.Ad.attributes['rooms'].astext == val)
                        conds.append(models.Ad.attributes['dynamic_data']['bedrooms'].astext.ilike(f"%{val}%"))
                        conds.append(models.Ad.attributes['dynamic_data']['rooms'].astext.ilike(f"%{val}%"))
            elif prefix == "bathrooms":
                for val in values:
                    if val == '+6':
                        conds.append(models.Ad.attributes['bathrooms'].astext == '+6')
                        conds.append(models.Ad.attributes['dynamic_data']['bathrooms'].astext.ilike('%6%'))
                        conds.append(models.Ad.attributes['dynamic_data']['bathrooms'].astext.ilike('%7%'))
                    else:
                        conds.append(models.Ad.attributes['bathrooms'].astext == val)
                        conds.append(models.Ad.attributes['dynamic_data']['bathrooms'].astext.ilike(f"%{val}%"))
            elif prefix == "furnished":
                for val in values:
                    conds.append(models.Ad.attributes['furnished'].astext == val)
                    conds.append(models.Ad.attributes['dynamic_data']['furnishing'].astext == val)
                    conds.append(models.Ad.attributes['dynamic_data']['furnished'].astext == val)
            elif prefix == "floor":
                for val in values:
                    conds.append(models.Ad.attributes['floor'].astext == val)
                    conds.append(models.Ad.attributes['dynamic_data']['floor'].astext == val)
            elif prefix == "age":
                for val in values:
                    conds.append(models.Ad.attributes['building_age'].astext == val)
                    conds.append(models.Ad.attributes['dynamic_data']['age'].astext == val)
                    conds.append(models.Ad.attributes['dynamic_data']['building_age'].astext == val)
            elif prefix == "rent_duration":
                for val in values:
                    conds.append(models.Ad.attributes['rent_duration'].astext == val)
                    conds.append(models.Ad.attributes['dynamic_data']['rent_duration'].astext == val)
            elif prefix in ["land_type", "zoning_classification", "facade", "geometric_shape", "topography", "ownership_type", "is_mortgaged", "installment_possible", "advertiser_type"]:
                for val in values:
                    conds.append(models.Ad.attributes['dynamic_data'][prefix].astext == val)
            elif prefix in ["payment_method", "transaction_type"]:
                for val in values:
                    conds.append(models.Ad.attributes[prefix].astext == val)
            elif prefix == "available_services":
                for val in values:
                    conds.append(models.Ad.attributes['dynamic_data']['available_services'].astext.ilike(f"%{val}%"))
            elif prefix == "main_features":
                for val in values:
                    conds = [
                        models.Ad.attributes['key_features'].astext.ilike(f"%{val}%"),
                        models.Ad.attributes['dynamic_data']['main_features'].astext.ilike(f"%{val}%"),
                        models.Ad.attributes['dynamic_data']['key_features'].astext.ilike(f"%{val}%"),
                        models.Ad.attributes['building_features'].astext.ilike(f"%{val}%")
                    ]
            elif prefix == "extra_features":
                for val in values:
                    conds.append(models.Ad.attributes['building_features'].astext.ilike(f"%{val}%"))
                    conds.append(models.Ad.attributes['dynamic_data']['extra_features'].astext.ilike(f"%{val}%"))
                    conds.append(models.Ad.attributes['dynamic_data']['building_features'].astext.ilike(f"%{val}%"))
            else:
                for val in values:
                    query = query.filter(models.Ad.linked_tags.any(models.Tag.name == f"{prefix}:{val}"))
                continue
                
            if conds:
                query = query.filter(or_(*conds))
                
        for t in generic_tags:
            tag_cond = models.Ad.linked_tags.any(models.Tag.name == t)
            attr_cond = or_(
                models.Ad.attributes['dynamic_data']['advertiser_type'].astext == t,
                models.Ad.attributes['payment_method'].astext == t,
                models.Ad.attributes['transaction_type'].astext == t,
                models.Ad.attributes['dynamic_data']['facade'].astext == t,
                models.Ad.attributes['dynamic_data']['land_type'].astext == t,
                models.Ad.attributes['dynamic_data']['ownership_type'].astext == t,
                models.Ad.attributes['dynamic_data']['zoning_classification'].astext == t,
                models.Ad.attributes['dynamic_data']['geometric_shape'].astext == t,
                models.Ad.attributes['dynamic_data']['topography'].astext == t,
                models.Ad.attributes['dynamic_data']['is_mortgaged'].astext == t,
                models.Ad.attributes['dynamic_data']['installment_possible'].astext == t,
            )
            query = query.filter(or_(tag_cond, attr_cond))
    
    # Optional support for the old section name method (for the homepage tabs)
    if section:
        query = query.join(models.Category).filter(models.Category.name == section)
        
    # Deep nested category logic
    if category_id:
        # Get all descendant category IDs efficiently in memory
        all_cats = db.query(models.Category.id, models.Category.parent_id).all()
        cat_graph = {}
        for c_id, p_id in all_cats:
            if p_id not in cat_graph:
                cat_graph[p_id] = []
            cat_graph[p_id].append(c_id)
            
        def get_descendants_fast(cat_id):
            descendants = [cat_id]
            if cat_id in cat_graph:
                for child_id in cat_graph[cat_id]:
                    descendants.extend(get_descendants_fast(child_id))
            return descendants
            
        all_cat_ids = get_descendants_fast(category_id)
        query = query.filter(models.Ad.category_id.in_(all_cat_ids))
        
    from sqlalchemy.orm import selectinload
    query = query.options(
        selectinload(models.Ad.linked_tags),
        selectinload(models.Ad.real_estate_detail)
    )
    
    # Define priority booleans for Postgres sorting
    has_image  = case((models.Ad.image_url != None, 1), else_=0)
    has_price  = case((models.Ad.price > 0, 1), else_=0)

    from sqlalchemy import case, func, text

    is_recent_organic = case(
        (
            (models.Ad.source_type == 'ORGANIC_USER') & 
            (models.Ad.created_at >= text("NOW() - INTERVAL '3 hours'")),
            0
        ),
        else_=1
    )

    row_num = func.row_number().over(
        partition_by=models.Ad.source_type,
        order_by=models.Ad.created_at.desc()
    )

    batch_size = case(
        (models.Ad.source_type == 'SCRAPER_BOT', 7.0),
        else_=3.0
    )

    batch_id = func.floor((row_num - 1) / batch_size)

    is_ai = case(
        (models.Ad.source_type == 'SCRAPER_BOT', 0),
        else_=1
    )

    if sort_by == 'price_asc':
        query = query.order_by(models.Ad.is_featured.desc(), effective_bid.desc(), models.Ad.price.asc(), models.Ad.id.desc())
    elif sort_by == 'price_desc':
        query = query.order_by(models.Ad.is_featured.desc(), effective_bid.desc(), models.Ad.price.desc(), models.Ad.id.desc())
    elif sort_by == 'oldest':
        query = query.order_by(models.Ad.is_featured.desc(), effective_bid.desc(), models.Ad.created_at.asc(), models.Ad.id.asc())
    elif sort_by == 'most_viewed':
        query = query.order_by(models.Ad.is_featured.desc(), effective_bid.desc(), models.Ad.views.desc(), models.Ad.id.desc())
    elif sort_by == 'nearest' and user_lat is not None and user_lng is not None:
        from sqlalchemy import func
        query = query.outerjoin(models.AdSearchIndex, models.Ad.id == models.AdSearchIndex.ad_id)
        query = query.outerjoin(models.Region, models.AdSearchIndex.region_id == models.Region.id)
        
        distance = func.sqrt(
            func.pow(models.Region.latitude - user_lat, 2) + 
            func.pow((models.Region.longitude - user_lng) * func.cos(user_lat * 3.14159 / 180.0), 2)
        )
        query = query.order_by(models.Ad.is_featured.desc(), effective_bid.desc(), distance.asc().nulls_last(), models.Ad.id.desc())
    elif sort_by == 'newest':
        query = query.order_by(models.Ad.is_featured.desc(), effective_bid.desc(), has_image.desc(), has_price.desc(), is_recent_organic.asc(), batch_id.asc(), is_ai.asc(), models.Ad.created_at.desc(), models.Ad.id.desc())
    elif sort_by == 'strict_newest':
        query = query.order_by(models.Ad.is_featured.desc(), effective_bid.desc(), is_recent_organic.asc(), batch_id.asc(), is_ai.asc(), models.Ad.created_at.desc(), models.Ad.id.desc())
    elif sort_by == 'premium_first':
        query = query.order_by(models.Ad.is_featured.desc(), effective_bid.desc(), models.Ad.is_hot.desc(), is_recent_organic.asc(), batch_id.asc(), is_ai.asc(), models.Ad.created_at.desc(), models.Ad.id.desc())
    elif sort_by == 'recommended' or sort_by is None:
        query = query.order_by(models.Ad.is_featured.desc(), effective_bid.desc(), models.Ad.is_hot.desc(), is_recent_organic.asc(), batch_id.asc(), is_ai.asc(), models.Ad.created_at.desc(), models.Ad.id.desc())
    else:
        query = query.order_by(models.Ad.is_featured.desc(), effective_bid.desc(), is_recent_organic.asc(), batch_id.asc(), is_ai.asc(), models.Ad.created_at.desc(), models.Ad.id.desc())
        
    ads = query.offset(skip).limit(limit).all()
    
    if current_user and ads:
        saved_ads = db.query(models.SavedAd.ad_id).filter(
            models.SavedAd.user_id == current_user.id,
            models.SavedAd.ad_id.in_([a.id for a in ads])
        ).all()
        saved_ids = {r[0] for r in saved_ads}
        for ad in ads:
            ad.is_saved = ad.id in saved_ids
            
    return ads





@app.get("/api/ads/aggregate", response_model=List[dict])
def aggregate_ads(
    group_by: str = Query("location", description="Field to group by: location, category_id"),
    category_id: int = None, 
    section: str = None, 
    search: str = None,
    location: List[str] = Query(None),
    min_price: float = None,
    max_price: float = None,
    is_hot: bool = None,
    is_published: bool = None,
    source_type: str = None,
    tags: List[str] = Query(None),
    only_others: bool = False,
    location_search: str = None,
    db: Session = Depends(get_db)
):
    from sqlalchemy import func, or_, cast, String, Integer
    # Use AdSearchIndex for maximum performance
    query = db.query(models.Ad).join(models.AdSearchIndex, models.Ad.id == models.AdSearchIndex.ad_id)
    
    if location_search:
        query = query.filter(models.Ad.location.ilike(f"%{location_search}%"))
        
    if only_others:
        query = query.filter(or_(
            models.Ad.location.ilike("%أخرى%"),
            models.Ad.location.ilike("%اخرى%"),
            models.Ad.location.ilike("%other%")
        ))
    
    if category_id:
        # Get all descendant category IDs efficiently in memory
        all_cats = db.query(models.Category.id, models.Category.parent_id).all()
        cat_graph = {}
        for c_id, p_id in all_cats:
            if p_id not in cat_graph:
                cat_graph[p_id] = []
            cat_graph[p_id].append(c_id)
            
        def get_descendants_fast(cat_id):
            descendants = [cat_id]
            if cat_id in cat_graph:
                for child_id in cat_graph[cat_id]:
                    descendants.extend(get_descendants_fast(child_id))
            return descendants
            
        all_cat_ids = get_descendants_fast(category_id)
        query = query.filter(models.AdSearchIndex.category_id.in_(all_cat_ids))
        
    if section:
        if section == 'rent':
            query = query.filter(models.AdSearchIndex.category_id.in_([3, 4])) # Real estate rent
        elif section == 'buy':
            query = query.filter(models.AdSearchIndex.category_id.in_([1, 2])) # Real estate buy
            
    if location and len(location) > 0:
        loc_filters = []
        for loc in location:
            loc_filters.append(models.Ad.location.ilike(f"%{loc}%"))
        query = query.filter(or_(*loc_filters))
        
    if min_price is not None:
        query = query.filter(models.AdSearchIndex.price >= min_price)
    if max_price is not None:
        query = query.filter(models.AdSearchIndex.price <= max_price)
        
    if is_hot is not None:
        query = query.filter(models.AdSearchIndex.is_hot == is_hot)
        
    if is_published is not None:
        query = query.filter(models.Ad.is_published == is_published)
    else:
        query = query.filter(models.Ad.is_published == True, models.Ad.is_sold == False)
        
    if not search:
        query = query.filter(models.Ad.image_url.isnot(None))
        query = query.filter(models.Ad.image_url != '[]')
        query = query.filter(models.Ad.image_url != '')
        
    if source_type:
        query = query.filter(models.Ad.source_type == source_type)
        
    if tags and len(tags) > 0:
        from collections import defaultdict
        grouped_tags = defaultdict(list)
        generic_tags = []
        for t in tags:
            if ":" in t:
                prefix, val = t.split(":", 1)
                vals = val.split(",")
                grouped_tags[prefix].extend(vals)
            else:
                generic_tags.append(t)
                
        for prefix, vals in grouped_tags.items():
            if prefix == "bedrooms":
                conditions = []
                for v in vals:
                    if v == '+6' or v == '6+':
                        conditions.extend([
                            models.Ad.attributes['rooms'].astext == '+6',
                            models.Ad.attributes['dynamic_data']['bedrooms'].astext.ilike('%6%'),
                            models.Ad.attributes['dynamic_data']['bedrooms'].astext.ilike('%7%'),
                            models.Ad.attributes['dynamic_data']['rooms'].astext.ilike('%6%'),
                            models.Ad.attributes['dynamic_data']['rooms'].astext.ilike('%7%')
                        ])
                    elif v == 'ستوديو':
                        conditions.extend([
                            models.Ad.attributes['rooms'].astext == '0',
                            models.Ad.attributes['rooms'].astext == 'ستوديو',
                            models.Ad.attributes['dynamic_data']['bedrooms'].astext.ilike('%ستوديو%'),
                            models.Ad.attributes['dynamic_data']['bedrooms'].astext.ilike('%0%'),
                            models.Ad.attributes['dynamic_data']['rooms'].astext.ilike('%ستوديو%'),
                            models.Ad.attributes['dynamic_data']['rooms'].astext.ilike('%0%')
                        ])
                    else:
                        conditions.extend([
                            models.Ad.attributes['rooms'].astext == v,
                            models.Ad.attributes['dynamic_data']['bedrooms'].astext.ilike(f"%{v}%"),
                            models.Ad.attributes['dynamic_data']['rooms'].astext.ilike(f"%{v}%")
                        ])
                query = query.filter(or_(*conditions))
            elif prefix == "bathrooms":
                conditions = []
                for v in vals:
                    if v == '+6' or v == '6+':
                        conditions.extend([
                            models.Ad.attributes['bathrooms'].astext == '+6',
                            models.Ad.attributes['dynamic_data']['bathrooms'].astext.ilike('%6%'),
                            models.Ad.attributes['dynamic_data']['bathrooms'].astext.ilike('%7%')
                        ])
                    else:
                        conditions.extend([
                            models.Ad.attributes['bathrooms'].astext == v,
                            models.Ad.attributes['dynamic_data']['bathrooms'].astext.ilike(f"%{v}%")
                        ])
                query = query.filter(or_(*conditions))
            elif prefix == "floor":
                conditions = []
                for v in vals:
                    conditions.extend([
                        models.Ad.attributes['floor'].astext == v,
                        models.Ad.attributes['dynamic_data']['floor'].astext == v
                    ])
                query = query.filter(or_(*conditions))
            elif prefix == "furnished":
                conditions = []
                for v in vals:
                    conditions.extend([
                        models.Ad.attributes['furnished'].astext == v,
                        models.Ad.attributes['dynamic_data']['furnishing'].astext == v,
                        models.Ad.attributes['dynamic_data']['furnished'].astext == v
                    ])
                query = query.filter(or_(*conditions))
            elif prefix == "min_area":
                v = int(vals[0]) if vals[0].isdigit() else 0
                if v > 0:
                    area_conds = [models.AdSearchIndex.build_area >= float(v)]
                    try:
                        numeric_area = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['area'].astext, '[^0-9]', '', 'g'), '')
                        area_conds.append(numeric_area.cast(Integer) >= v)
                        numeric_barea = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['building_area'].astext, '[^0-9]', '', 'g'), '')
                        area_conds.append(numeric_barea.cast(Integer) >= v)
                        numeric_larea = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['land_area'].astext, '[^0-9]', '', 'g'), '')
                        area_conds.append(numeric_larea.cast(Integer) >= v)
                        numeric_area_top = func.nullif(func.regexp_replace(models.Ad.attributes['area'].astext, '[^0-9]', '', 'g'), '')
                        area_conds.append(numeric_area_top.cast(Integer) >= v)
                    except: pass
                    query = query.filter(or_(*area_conds))
            elif prefix == "max_area":
                v = int(vals[0]) if vals[0].isdigit() else 0
                if v > 0:
                    area_conds = [models.AdSearchIndex.build_area <= float(v)]
                    try:
                        numeric_area = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['area'].astext, '[^0-9]', '', 'g'), '')
                        area_conds.append(numeric_area.cast(Integer) <= v)
                        numeric_barea = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['building_area'].astext, '[^0-9]', '', 'g'), '')
                        area_conds.append(numeric_barea.cast(Integer) <= v)
                        numeric_larea = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['land_area'].astext, '[^0-9]', '', 'g'), '')
                        area_conds.append(numeric_larea.cast(Integer) <= v)
                        numeric_area_top = func.nullif(func.regexp_replace(models.Ad.attributes['area'].astext, '[^0-9]', '', 'g'), '')
                        area_conds.append(numeric_area_top.cast(Integer) <= v)
                    except: pass
                    query = query.filter(or_(*area_conds))
            elif prefix == "period":
                query = query.filter(cast(models.AdSearchIndex.search_text, String).ilike(f"%period:{vals[0]}%"))
            else:
                for v in vals:
                    query = query.filter(cast(models.AdSearchIndex.attributes_jsonb, String).ilike(f"%{prefix}:{v}%"))
                    
        for t in generic_tags:
            query = query.filter(cast(models.AdSearchIndex.attributes_jsonb, String).ilike(f"%{t}%"))
            
    if group_by == 'location':
        from sqlalchemy import case
        results = query.with_entities(
            models.Ad.location,
            func.count(models.Ad.id),
            func.sum(case((models.Ad.market_price_status == 'BELOW_MARKET', 1), else_=0)),
            func.avg(models.AdSearchIndex.price),
            func.avg(models.AdSearchIndex.build_area)
        ).group_by(models.Ad.location).all()
        
        return [{
            "group": row[0] or "Unknown",
            "count": row[1] or 0,
            "below_market_count": row[2] or 0,
            "avg_price": float(row[3]) if row[3] is not None else 0.0,
            "avg_area": float(row[4]) if row[4] is not None else 0.0,
        } for row in results]
    elif group_by == 'category_id':
        results = query.with_entities(models.AdSearchIndex.category_id, func.count(models.Ad.id)).group_by(models.AdSearchIndex.category_id).all()
        return [{"group": str(row[0]), "count": row[1]} for row in results]
    
    return []


@app.get("/api/ads/count", response_model=dict)
def get_ads_count(
    category_id: int = None, 
    section: str = None, 
    search: str = None,
    location: List[str] = Query(None),
    min_price: float = None,
    max_price: float = None,
    is_hot: bool = None,
    is_published: bool = None,
    source_type: str = None,
    tags: List[str] = Query(None),
    only_others: bool = False,
    location_search: str = None,
    phone: str = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Ad)
    
    if location_search:
        query = query.filter(models.Ad.location.ilike(f"%{location_search}%"))
        
    if phone:
        from sqlalchemy import cast, String
        query = query.outerjoin(models.User, models.Ad.user_id == models.User.id)
        query = query.filter(or_(
            models.User.phone.ilike(f"%{phone}%"), 
            models.User.mobile_number.ilike(f"%{phone}%"),
            cast(models.Ad.attributes, String).ilike(f"%{phone}%")
        ))
        
    if only_others:
        query = query.filter(or_(
            models.Ad.location.ilike("%أخرى%"),
            models.Ad.location.ilike("%اخرى%"),
            models.Ad.location.ilike("%other%")
        ))
    
    ignore_location = False
    if search:
        try:
            from search_parser import QueryParserService
            parsed = QueryParserService.parse(search)
            if parsed.location:
                ignore_location = True
        except:
            pass
    if search:
        ranked_ad_ids = SearchService.search_properties(db, search, limit=1000)
        
        if not ranked_ad_ids:
            return {"total_count": 0}
            
        query = query.filter(models.Ad.id.in_(ranked_ad_ids))
        
    if location and not ignore_location:
        parent_loc = None
        target_locs = []
        
        first_loc = location[0]
        if first_loc == "محافظة العاصمة": first_loc = "عمان"
        elif first_loc.startswith("محافظة "): first_loc = first_loc.replace("محافظة ", "")
        
        target_loc_norm = norm_str(first_loc)
        city = db.query(models.City).filter(norm_col(models.City.name_ar) == target_loc_norm).first()
        if city:
            parent_loc = target_loc_norm
            target_locs = location[1:]
        else:
            target_locs = location
            
        filters = []
        if parent_loc and not target_locs:
            filters.append(norm_col(models.Ad.location).ilike(f"{parent_loc}%"))
        elif parent_loc and target_locs:
            for t_loc in target_locs:
                if t_loc == "محافظة العاصمة": t_loc = "عمان"
                elif t_loc.startswith("محافظة "): t_loc = t_loc.replace("محافظة ", "")
                t_loc_norm = norm_str(t_loc)
                
                if t_loc_norm == norm_str("أخرى"):
                    filters.append(norm_col(models.Ad.location).ilike(f"{parent_loc}, أخرى%"))
                    filters.append(norm_col(models.Ad.location).ilike(f"{parent_loc}, other%"))
                else:
                    if t_loc_norm.startswith("ال"):
                        filters.append(norm_col(models.Ad.location).ilike(f"{parent_loc}, {t_loc_norm}%"))
                        filters.append(norm_col(models.Ad.location).ilike(f"{parent_loc}, {t_loc_norm[2:]}%"))
                    else:
                        filters.append(norm_col(models.Ad.location).ilike(f"{parent_loc}, {t_loc_norm}%"))
                        filters.append(norm_col(models.Ad.location).ilike(f"{parent_loc}, ال{t_loc_norm}%"))
        else:
            for t_loc in target_locs:
                if t_loc == "محافظة العاصمة": t_loc = "عمان"
                elif t_loc.startswith("محافظة "): t_loc = t_loc.replace("محافظة ", "")
                t_loc_norm = norm_str(t_loc)
                
                if t_loc_norm == norm_str("أخرى"):
                    filters.append(norm_col(models.Ad.location).ilike(f"%أخرى%"))
                    filters.append(norm_col(models.Ad.location).ilike(f"%other%"))
                else:
                    if t_loc_norm.startswith("ال"):
                        filters.append(norm_col(models.Ad.location).ilike(f"%{t_loc_norm}%"))
                        filters.append(norm_col(models.Ad.location).ilike(f"%{t_loc_norm[2:]}%"))
                    else:
                        filters.append(norm_col(models.Ad.location).ilike(f"%{t_loc_norm}%"))
                        filters.append(norm_col(models.Ad.location).ilike(f"%ال{t_loc_norm}%"))
                    
        if filters:
            query = query.filter(or_(*filters))
        
    if min_price is not None:
        query = query.filter(models.Ad.price >= min_price)
        
    if max_price is not None:
        query = query.filter(models.Ad.price <= max_price)
        
    if is_hot is not None:
        query = query.filter(models.Ad.is_hot == is_hot)
        
    if is_published is not None:
        query = query.filter(models.Ad.is_published == is_published)
    else:
        query = query.filter(models.Ad.is_published == True, models.Ad.is_sold == False)
        
    # Filter out ads without images on the home page (general feed)
    if not search:
        query = query.filter(models.Ad.image_url.isnot(None))
        query = query.filter(models.Ad.image_url != '[]')
        query = query.filter(models.Ad.image_url != '')
        
    if source_type:
        query = query.filter(models.Ad.source_type == source_type)
        
    if tags:
        from sqlalchemy import Integer
        from collections import defaultdict
        
        grouped_tags = defaultdict(list)
        generic_tags = []
        for t in tags:
            if ":" in t:
                prefix, val = t.split(":", 1)
                grouped_tags[prefix].append(val)
            else:
                generic_tags.append(t)
                
        for prefix, values in grouped_tags.items():
            conds = []
            if prefix == "max_price":
                for val in values:
                    query = query.filter(models.Ad.price <= float(val))
                continue
            elif prefix == "min_price":
                for val in values:
                    query = query.filter(models.Ad.price >= float(val))
                continue
            elif prefix == "min_area":
                from sqlalchemy import func
                for val in values:
                    try:
                        v = int(val)
                        numeric_area = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['area'].astext, '[^0-9]', '', 'g'), '')
                        conds.append(numeric_area.cast(Integer) >= v)
                        numeric_barea = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['building_area'].astext, '[^0-9]', '', 'g'), '')
                        conds.append(numeric_barea.cast(Integer) >= v)
                        numeric_larea = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['land_area'].astext, '[^0-9]', '', 'g'), '')
                        conds.append(numeric_larea.cast(Integer) >= v)
                        numeric_area_top = func.nullif(func.regexp_replace(models.Ad.attributes['area'].astext, '[^0-9]', '', 'g'), '')
                        conds.append(numeric_area_top.cast(Integer) >= v)
                    except: pass
            elif prefix == "max_area":
                from sqlalchemy import func
                for val in values:
                    try:
                        v = int(val)
                        numeric_area = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['area'].astext, '[^0-9]', '', 'g'), '')
                        conds.append(numeric_area.cast(Integer) <= v)
                        numeric_barea = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['building_area'].astext, '[^0-9]', '', 'g'), '')
                        conds.append(numeric_barea.cast(Integer) <= v)
                        numeric_larea = func.nullif(func.regexp_replace(models.Ad.attributes['dynamic_data']['land_area'].astext, '[^0-9]', '', 'g'), '')
                        conds.append(numeric_larea.cast(Integer) <= v)
                        numeric_area_top = func.nullif(func.regexp_replace(models.Ad.attributes['area'].astext, '[^0-9]', '', 'g'), '')
                        conds.append(numeric_area_top.cast(Integer) <= v)
                    except: pass
            elif prefix == "area":
                for val in values:
                    conds.append(models.Ad.attributes['area'].astext.ilike(f"%{val}%"))
                    conds.append(models.Ad.attributes['dynamic_data']['area'].astext.ilike(f"%{val}%"))
                    conds.append(models.Ad.attributes['dynamic_data']['building_area'].astext.ilike(f"%{val}%"))
                    conds.append(models.Ad.attributes['dynamic_data']['land_area'].astext.ilike(f"%{val}%"))
            elif prefix == "bedrooms":
                for val in values:
                    if val == '+6':
                        conds.append(models.Ad.attributes['rooms'].astext == '+6')
                        conds.append(models.Ad.attributes['dynamic_data']['bedrooms'].astext.ilike('%6%'))
                        conds.append(models.Ad.attributes['dynamic_data']['bedrooms'].astext.ilike('%7%'))
                        conds.append(models.Ad.attributes['dynamic_data']['rooms'].astext.ilike('%6%'))
                        conds.append(models.Ad.attributes['dynamic_data']['rooms'].astext.ilike('%7%'))
                    elif val == 'ستوديو':
                        conds.append(models.Ad.attributes['rooms'].astext == '0')
                        conds.append(models.Ad.attributes['rooms'].astext == 'ستوديو')
                        conds.append(models.Ad.attributes['dynamic_data']['bedrooms'].astext.ilike('%ستوديو%'))
                        conds.append(models.Ad.attributes['dynamic_data']['bedrooms'].astext.ilike('%0%'))
                        conds.append(models.Ad.attributes['dynamic_data']['rooms'].astext.ilike('%ستوديو%'))
                        conds.append(models.Ad.attributes['dynamic_data']['rooms'].astext.ilike('%0%'))
                    else:
                        conds.append(models.Ad.attributes['rooms'].astext == val)
                        conds.append(models.Ad.attributes['dynamic_data']['bedrooms'].astext.ilike(f"%{val}%"))
                        conds.append(models.Ad.attributes['dynamic_data']['rooms'].astext.ilike(f"%{val}%"))
            elif prefix == "bathrooms":
                for val in values:
                    if val == '+6':
                        conds.append(models.Ad.attributes['bathrooms'].astext == '+6')
                        conds.append(models.Ad.attributes['dynamic_data']['bathrooms'].astext.ilike('%6%'))
                        conds.append(models.Ad.attributes['dynamic_data']['bathrooms'].astext.ilike('%7%'))
                    else:
                        conds.append(models.Ad.attributes['bathrooms'].astext == val)
                        conds.append(models.Ad.attributes['dynamic_data']['bathrooms'].astext.ilike(f"%{val}%"))
            elif prefix == "furnished":
                for val in values:
                    conds.append(models.Ad.attributes['furnished'].astext == val)
                    conds.append(models.Ad.attributes['dynamic_data']['furnishing'].astext == val)
                    conds.append(models.Ad.attributes['dynamic_data']['furnished'].astext == val)
            elif prefix == "floor":
                for val in values:
                    conds.append(models.Ad.attributes['floor'].astext == val)
                    conds.append(models.Ad.attributes['dynamic_data']['floor'].astext == val)
            elif prefix == "age":
                for val in values:
                    conds.append(models.Ad.attributes['building_age'].astext == val)
                    conds.append(models.Ad.attributes['dynamic_data']['age'].astext == val)
                    conds.append(models.Ad.attributes['dynamic_data']['building_age'].astext == val)
            elif prefix == "rent_duration":
                for val in values:
                    conds.append(models.Ad.attributes['rent_duration'].astext == val)
                    conds.append(models.Ad.attributes['dynamic_data']['rent_duration'].astext == val)
            elif prefix in ["land_type", "zoning_classification", "facade", "geometric_shape", "topography", "ownership_type", "is_mortgaged", "installment_possible"]:
                for val in values:
                    conds.append(models.Ad.attributes['dynamic_data'][prefix].astext == val)
            elif prefix == "available_services":
                for val in values:
                    conds.append(models.Ad.attributes['dynamic_data']['available_services'].astext.ilike(f"%{val}%"))
            elif prefix == "main_features":
                for val in values:
                    conds = [
                        models.Ad.attributes['key_features'].astext.ilike(f"%{val}%"),
                        models.Ad.attributes['dynamic_data']['main_features'].astext.ilike(f"%{val}%"),
                        models.Ad.attributes['dynamic_data']['key_features'].astext.ilike(f"%{val}%"),
                        models.Ad.attributes['building_features'].astext.ilike(f"%{val}%")
                    ]
            elif prefix == "extra_features":
                for val in values:
                    conds.append(models.Ad.attributes['building_features'].astext.ilike(f"%{val}%"))
                    conds.append(models.Ad.attributes['dynamic_data']['extra_features'].astext.ilike(f"%{val}%"))
                    conds.append(models.Ad.attributes['dynamic_data']['building_features'].astext.ilike(f"%{val}%"))
            else:
                for val in values:
                    query = query.filter(models.Ad.linked_tags.any(models.Tag.name == f"{prefix}:{val}"))
                continue
                
            if conds:
                query = query.filter(or_(*conds))
                
        for t in generic_tags:
            query = query.filter(models.Ad.linked_tags.any(models.Tag.name == t))
    
    if section:
        query = query.join(models.Category).filter(models.Category.name == section)
        
    if category_id:
        # Get all descendant category IDs efficiently in memory
        all_cats = db.query(models.Category.id, models.Category.parent_id).all()
        cat_graph = {}
        for c_id, p_id in all_cats:
            if p_id not in cat_graph:
                cat_graph[p_id] = []
            cat_graph[p_id].append(c_id)
            
        def get_descendants_fast(cat_id):
            descendants = [cat_id]
            if cat_id in cat_graph:
                for child_id in cat_graph[cat_id]:
                    descendants.extend(get_descendants_fast(child_id))
            return descendants
            
        all_cat_ids = get_descendants_fast(category_id)
        query = query.filter(models.Ad.category_id.in_(all_cat_ids))
        
    total_count = query.count()
    total_count = query.count()
    return {"total_count": total_count}

@app.post("/api/ads/draft", response_model=schemas.Ad, dependencies=[Depends(auth.get_rate_limiter(20, 60))])
def create_ad_draft(
    ad_draft: schemas.AdDraftCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    user_id = current_user.id
    ad_data = ad_draft.model_dump()
    re_detail_data = ad_data.pop("real_estate_detail", None)
    tags_data = ad_data.pop("linked_tags", [])
    image_urls = ad_data.pop("image_urls", [])
    ad_data.pop("phone_number", None)
    
    attributes = ad_data.get("attributes") or {}
    attributes["image_urls"] = image_urls
    ad_data["attributes"] = attributes

    if image_urls:
        ad_data["image_url"] = image_urls[0]

    db_ad = models.Ad(
        **ad_data,
        user_id=user_id,
        is_published=False
    )
    
    if tags_data:
        for tag_name in tags_data:
            tag = db.query(models.Tag).filter(models.Tag.name == tag_name).first()
            if not tag:
                tag = models.Tag(name=tag_name)
                db.add(tag)
            db_ad.linked_tags.append(tag)
            
    db.add(db_ad)
    db.commit()
    db.refresh(db_ad)
    
    if re_detail_data:
        re_detail = models.AdRealEstateDetail(**re_detail_data, ad_id=db_ad.id)
        db.add(re_detail)
        db.commit()
        db.refresh(db_ad)
        
    return db_ad

@app.put("/api/ads/{ad_id}/draft", response_model=schemas.Ad)
def update_ad_draft(
    ad_id: int,
    request: Request,
    ad_draft: schemas.AdDraftUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    db_ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not db_ad:
        raise HTTPException(status_code=404, detail="Ad not found")
        
    user_id = current_user.id
            
    if db_ad.user_id != user_id and current_user.user_type != "admin":
        log_bola_attempt(str(user_id), get_real_ip(request), request.url.path, str(ad_id))
        raise HTTPException(status_code=403, detail="Not authorized to edit this ad")

    if db_ad.is_published:
        # Prevent draft autosaves from modifying published ads. 
        # This prevents the frontend's Wizard dispose() callbacks from 
        # overwriting the ad with stale data (like wiping image_urls) right after publishing.
        return db_ad

    update_data = ad_draft.model_dump(exclude_unset=True)
    re_detail_data = update_data.pop("real_estate_detail", None)
    tags_data = update_data.pop("linked_tags", None)
    image_urls = update_data.pop("image_urls", None)
    update_data.pop("phone_number", None)

    attributes = db_ad.attributes or {}
    if image_urls is not None:
        attributes["image_urls"] = image_urls
        if image_urls:
            update_data["image_url"] = image_urls[0]

    new_attrs = update_data.pop("attributes", None)
    if new_attrs:
        # Protect image_urls from being wiped by stale frontend attributes dictionary
        existing_images = attributes.get("image_urls", [])
        if "image_urls" in new_attrs:
            incoming_images = new_attrs["image_urls"]
            if not incoming_images and existing_images:
                del new_attrs["image_urls"]
        attributes.update(new_attrs)
        
    update_data["attributes"] = attributes

    for key, value in update_data.items():
        if key == "is_published" and value is True:
            if not attributes.get("image_urls") or len(attributes.get("image_urls", [])) < 0:
                raise HTTPException(
                    status_code=400,
                    detail="لابد من رفع 3 صور على الأقل لنشر الإعلان"
                )
        setattr(db_ad, key, value)
        
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(db_ad, "attributes")

    if tags_data is not None:
        db_ad.linked_tags.clear()
        for tag_name in tags_data:
            tag = db.query(models.Tag).filter(models.Tag.name == tag_name).first()
            if not tag:
                tag = models.Tag(name=tag_name)
                db.add(tag)
            db_ad.linked_tags.append(tag)

    if re_detail_data is not None:
        if db_ad.real_estate_detail:
            for k, v in re_detail_data.items():
                setattr(db_ad.real_estate_detail, k, v)
        else:
            re_detail = models.AdRealEstateDetail(**re_detail_data, ad_id=db_ad.id)
            db.add(re_detail)

    db.commit()
    db.refresh(db_ad)
    return db_ad


def process_new_ad_background(ad_id: int):
    from database import SessionLocal
    from duplicate_detection_router import check_duplicates
    from market_analysis_service import MarketAnalysisService
    import logging
    logger = logging.getLogger(__name__)
    
    db = SessionLocal()
    try:
        # 1. Check duplicates
        try:
            check_duplicates(ad_id, db)
            db.commit()
        except Exception as e:
            logger.error(f"Error checking duplicates for ad {ad_id}: {e}")
            
        # 2. Market Analysis
        try:
            MarketAnalysisService.calculate_and_save(ad_id, db)
            db.commit()
        except Exception as e:
            logger.error(f"Error analyzing market for ad {ad_id}: {e}")
    finally:
        db.close()

@app.post("/api/ads", response_model=schemas.Ad)
def create_ad(
    ad: schemas.AdCreate, 
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    user_id = current_user.id
    user_phone = ad.phone_number or current_user.mobile_number

    # Validate image count
    if not ad.image_urls or len(image_urls) < 0:
        raise HTTPException(
            status_code=400,
            detail="A minimum of 3 images is required to publish an ad."
        )

    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    # --- Duplicate & Spam Prevention ---
    if user and user.id != 1:
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        
        # 1. Ban Check
        if user.banned_from_posting_until and user.banned_from_posting_until > now:
            raise HTTPException(
                status_code=403, 
                detail=f"أنت محظور من إضافة الإعلانات حتى {user.banned_from_posting_until.strftime('%Y-%m-%d %H:%M:%S')} بسبب تكرار المخالفات."
            )
            
        # 2. Fetch All Active Ads for AI comparison
        recent_ads = db.query(models.Ad).filter(
            models.Ad.user_id == user.id,
            models.Ad.is_published == True,
            models.Ad.is_paused == False,
            models.Ad.is_sold == False,
            models.Ad.is_rejected == False
        ).all()
        
        if recent_ads:
            from duplicate_checker import check_duplicate_with_deepseek
            ad_dict = ad.model_dump()
            is_duplicate = check_duplicate_with_deepseek(ad_dict, recent_ads)
            
            if is_duplicate:
                # 3. Handle Penalty State Machine
                if not user.first_duplicate_attempt_at or (now - user.first_duplicate_attempt_at) > timedelta(minutes=30):
                    user.first_duplicate_attempt_at = now
                    user.duplicate_attempts = 1
                else:
                    user.duplicate_attempts += 1
                    
                if user.duplicate_attempts >= 5:
                    # Apply Escalating Ban
                    if user.last_penalty_at:
                        days_since_last = (now - user.last_penalty_at).days
                        if user.penalty_tier == 1 and days_since_last > 7:
                            user.penalty_tier = 0
                        elif user.penalty_tier >= 2 and days_since_last > 30:
                            user.penalty_tier = 0
                            
                    user.penalty_tier += 1
                    
                    if user.penalty_tier == 1:
                        ban_duration = timedelta(hours=6)
                        ban_str = "6 ساعات"
                    elif user.penalty_tier == 2:
                        ban_duration = timedelta(days=3)
                        ban_str = "3 أيام"
                    elif user.penalty_tier == 3:
                        ban_duration = timedelta(days=30)
                        ban_str = "شهر واحد"
                    else:
                        ban_duration = timedelta(days=365)
                        ban_str = "سنة كاملة"
                        
                    user.banned_from_posting_until = now + ban_duration
                    user.last_penalty_at = now
                    user.duplicate_attempts = 0
                    db.commit()
                    
                    raise HTTPException(
                        status_code=403,
                        detail=f"تم حظرك من إضافة الإعلانات لمدة {ban_str} لتجاوزك الحد المسموح للإعلانات المكررة."
                    )
                else:
                    db.commit()
                    remaining = 5 - user.duplicate_attempts
                    raise HTTPException(
                        status_code=400,
                        detail=f"إعلان مكرر! يرجى عدم تكرار نشر نفس الإعلان. لديك {remaining} محاولات متبقية قبل الحظر المؤقت."
                    )

    ad_data = ad.model_dump()
    re_detail_data = ad_data.pop("real_estate_detail", None)
    tags_data = ad_data.pop("linked_tags", [])
    
    image_urls = ad_data.pop("image_urls", [])
    if len(image_urls) < 0:
        raise HTTPException(
            status_code=400,
            detail="A minimum of 3 images is required to publish an ad."
        )
    
    # We must explicitly pop phone_number and rooms to prevent SQLAlchemy from crashing as they are not columns
    ad_data.pop("phone_number", None)
    ad_data.pop("rooms", None)
    
    attributes = ad_data.get("attributes") or {}
    attributes["image_urls"] = image_urls
    if user_phone:
        attributes["phone_number"] = user_phone
        
    if image_urls:
        ad_data["image_url"] = image_urls[0]
        
    dynamic_data = attributes.get("dynamic_data", {})
    if dynamic_data:
        import re
        if "bedrooms" in dynamic_data:
            nums = re.findall(r'\d+', str(dynamic_data["bedrooms"]))
            if nums: attributes["rooms"] = int(nums[0])
        if "bathrooms" in dynamic_data:
            nums = re.findall(r'\d+', str(dynamic_data["bathrooms"]))
            if nums: attributes["bathrooms"] = int(nums[0])
        if "furnishing" in dynamic_data: attributes["furnished"] = dynamic_data["furnishing"]
        if "floor" in dynamic_data: attributes["floor"] = dynamic_data["floor"]
        if "age" in dynamic_data: attributes["building_age"] = dynamic_data["age"]
        if "rent_duration" in dynamic_data: attributes["rent_duration"] = dynamic_data["rent_duration"]
        if "main_features" in dynamic_data: attributes["key_features"] = dynamic_data["main_features"]
        if "extra_features" in dynamic_data: attributes["building_features"] = dynamic_data["extra_features"]
        if "nearby" in dynamic_data: attributes["nearby_places"] = dynamic_data["nearby"]
            
    if "city" in attributes and "region" in attributes:
        ad_data["location"] = f"{attributes['city']}, {attributes['region']}"
    elif "location" in ad_data and ad_data["location"]:
        loc = ad_data["location"]
        if "،" in loc or "," in loc:
            parts = [p.strip() for p in loc.replace("،", ",").split(",")]
            if len(parts) == 2:
                city_names = {"عمان", "إربد", "اربد", "الزرقاء", "زرقاء", "المفرق", "مفرق", "جرش", "عجلون", "البلقاء", "مادبا", "الكرك", "كرك", "الطفيلة", "طفيلة", "معان", "العقبة", "عقبة", "محافظة العاصمة"}
                if parts[1] in city_names:
                    ad_data["location"] = f"{parts[1]}, {parts[0]}"

    ad_data["attributes"] = attributes
    
    db_ad = models.Ad(
        **ad_data,
        user_id=user_id,
        is_published=True
    )
    
    # Process Tags
    if tags_data:
        for tag_name in tags_data:
            tag = db.query(models.Tag).filter(models.Tag.name == tag_name).first()
            if not tag:
                tag = models.Tag(name=tag_name)
                db.add(tag)
            db_ad.linked_tags.append(tag)
            
    db.add(db_ad)
    db.commit()
    db.refresh(db_ad)
    
    # Process Real Estate Details
    if re_detail_data:
        new_re_detail = models.AdRealEstateDetail(ad_id=db_ad.id, **re_detail_data)
        db.add(new_re_detail)
        db.commit()
        db.refresh(db_ad)

    # Notify: Ad submitted confirmation to the owner
    background_tasks.add_task(process_new_ad_background, db_ad.id)
    background_tasks.add_task(
        send_personal_notification,
        target_user_id=db_ad.user_id,
        title="تم نشر إعلانك بنجاح ✅",
        body=f"إعلانك '{db_ad.title[:50]}' تم نشره بنجاح وأصبح متاحاً للجميع.",
        notification_type="ad_created",
        reference_id=db_ad.id
    )
    
    # Sync to search index
    SearchService.sync_ad_to_search_index(db, db_ad)

    # Trigger saved searches alerts
    from observer import trigger_saved_filter_notifications
    background_tasks.add_task(trigger_saved_filter_notifications, db, db_ad)
    
    # Check Category Milestones for notifications
    background_tasks.add_task(check_category_milestone_task, db_ad.category_id)

    db_ad.message = "تم نشر إعلانك بنجاح! قد يستغرق ظهوره في نتائج البحث بضع دقائق."

    return db_ad

@app.put("/api/ads/{ad_id}", response_model=schemas.Ad)
def update_ad(
    ad_id: int,
    request: Request,
    ad_update: schemas.AdUpdate,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    db_ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not db_ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    # Ownership check: only owner or admin may update
    if db_ad.user_id != current_user.id and current_user.user_type != "admin":
        log_bola_attempt(str(current_user.id), get_real_ip(request), request.url.path, str(ad_id))
        raise HTTPException(status_code=403, detail="Not authorized to edit this ad")

    update_dict = ad_update.model_dump(exclude_unset=True)
    re_detail_data = update_dict.pop("real_estate_detail", None)
    tags_data = update_dict.pop("linked_tags", [])
    
    image_urls_updated = False
    if "image_urls" in update_dict:
        image_urls = update_dict.pop("image_urls")
        if len(image_urls) < 0:
            raise HTTPException(
                status_code=400,
                detail="A minimum of 3 images is required to publish an ad."
            )
        image_urls_updated = True

    update_dict.pop("phone_number", None)
    update_dict.pop("rooms", None)
    
    attributes = update_dict.get("attributes", {})
    
    if "city" in attributes and "region" in attributes:
        update_dict["location"] = f"{attributes['city']}, {attributes['region']}"
    elif "location" in update_dict and update_dict["location"]:
        loc = update_dict["location"]
        if "،" in loc or "," in loc:
            parts = [p.strip() for p in loc.replace("،", ",").split(",")]
            if len(parts) == 2:
                city_names = {"عمان", "إربد", "اربد", "الزرقاء", "زرقاء", "المفرق", "مفرق", "جرش", "عجلون", "البلقاء", "مادبا", "الكرك", "كرك", "الطفيلة", "طفيلة", "معان", "العقبة", "عقبة", "محافظة العاصمة"}
                if parts[1] in city_names:
                    update_dict["location"] = f"{parts[1]}, {parts[0]}"

    attributes = update_dict.get("attributes") or {}
    
    # Protect image_urls from being wiped by stale frontend attributes dictionary
    existing_images = db_ad.attributes.get("image_urls", []) if db_ad.attributes else []
    if "image_urls" in attributes:
        incoming_images = attributes["image_urls"]
        if not incoming_images and existing_images:
            del attributes["image_urls"]
            
    if image_urls_updated:
        attributes["image_urls"] = image_urls
    
    dynamic_data = attributes.get("dynamic_data", {})
    if dynamic_data:
        import re
        if "bedrooms" in dynamic_data:
            nums = re.findall(r'\d+', str(dynamic_data["bedrooms"]))
            if nums: attributes["rooms"] = int(nums[0])
        if "bathrooms" in dynamic_data:
            nums = re.findall(r'\d+', str(dynamic_data["bathrooms"]))
            if nums: attributes["bathrooms"] = int(nums[0])
        if "furnishing" in dynamic_data: attributes["furnished"] = dynamic_data["furnishing"]
        if "floor" in dynamic_data: attributes["floor"] = dynamic_data["floor"]
        if "age" in dynamic_data: attributes["building_age"] = dynamic_data["age"]
        if "rent_duration" in dynamic_data: attributes["rent_duration"] = dynamic_data["rent_duration"]
        if "main_features" in dynamic_data: attributes["key_features"] = dynamic_data["main_features"]
        if "extra_features" in dynamic_data: attributes["building_features"] = dynamic_data["extra_features"]
        if "nearby" in dynamic_data: attributes["nearby_places"] = dynamic_data["nearby"]
            
    update_dict["attributes"] = attributes
    
    if image_urls_updated and image_urls:
        update_dict["image_url"] = image_urls[0]

    # Handle automatic region creation if location specifies a new region
    if "location" in update_dict and update_dict["location"]:
        loc_str = update_dict["location"].strip()
        loc_str = loc_str.replace("،", ",").replace("-", ",").replace(" - ", ",")
        if "," in loc_str:
            parts = [p.strip() for p in loc_str.split(",")]
            if len(parts) >= 2:
                city_name = parts[0]
                region_name = parts[1]
                
                c_norm = norm_str(city_name)
                if c_norm == norm_str("محافظة العاصمة"): c_norm = norm_str("عمان")
                elif c_norm.startswith(norm_str("محافظة ")): c_norm = c_norm.replace(norm_str("محافظة "), "")
                
                city = db.query(models.City).filter(norm_col(models.City.name_ar) == c_norm).first()
                if city:
                    r_norm = normalize_region_name(region_name)
                    region = db.query(models.Region).filter(
                        models.Region.city_id == city.id,
                        norm_region_col(models.Region.name_ar) == r_norm
                    ).first()
                    
                    if not region:
                        # Fallback to other if region doesn't exist to prevent duplicates
                        update_dict["location"] = f"{city_name}, أخرى"
                    else:
                        update_dict["location"] = f"{city.name_ar}, {region.name_ar}"

    was_unpublished = not db_ad.is_published
    
    for key, value in update_dict.items():
        if hasattr(db_ad, key) and key not in ['id', 'user_id', 'created_at', 'is_hot', 'is_rejected', 'views', 'favorites_count', 'chats_count', 'source_type']:
            setattr(db_ad, key, value)
            
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(db_ad, "attributes")
            
    is_now_published = db_ad.is_published
            
    # Process Tags
    if tags_data:
        db_ad.linked_tags = []
        for tag_name in tags_data:
            tag = db.query(models.Tag).filter(models.Tag.name == tag_name).first()
            if not tag:
                tag = models.Tag(name=tag_name)
                db.add(tag)
            db_ad.linked_tags.append(tag)

    if re_detail_data is not None:
        if db_ad.real_estate_detail:
            for r_key, r_val in re_detail_data.items():
                if hasattr(db_ad.real_estate_detail, r_key) and r_key not in ['id', 'ad_id']:
                    setattr(db_ad.real_estate_detail, r_key, r_val)
        else:
            new_re_detail = models.AdRealEstateDetail(ad_id=db_ad.id, **re_detail_data)
            db.add(new_re_detail)
            
    db.commit()
    db.refresh(db_ad)
    
    # Sync to search index
    SearchService.sync_ad_to_search_index(db, db_ad)
    
    # Notify: Ad submitted confirmation to the owner if transitioned from unpublished to published
    if was_unpublished and is_now_published:
        background_tasks.add_task(
            send_personal_notification,
            target_user_id=db_ad.user_id,
            title="تم نشر إعلانك بنجاح ✅",
            body=f"إعلانك '{db_ad.title[:50]}' تم نشره بنجاح وأصبح متاحاً للجميع.",
            notification_type="ad_created",
            reference_id=db_ad.id
        )
    
    background_tasks.add_task(process_new_ad_background, db_ad.id)
    return db_ad

@app.post("/api/ads/{ad_id}/bid", response_model=schemas.Ad, dependencies=[Depends(auth.get_rate_limiter(10, 60))])
def set_ad_bid(
    ad_id: int, 
    bid_request: schemas.AdBidRequest, 
    current_user: models.User = Depends(auth.get_current_user), 
    db: Session = Depends(get_db)
):
    ad = db.query(models.Ad).filter(models.Ad.id == ad_id, models.Ad.user_id == current_user.id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
        
    if bid_request.cpc_bid > 0:
        if bid_request.cpc_bid < 0.07:
            raise HTTPException(status_code=400, detail="Minimum bid must be 0.07 JOD")
        if bid_request.cpc_bid > 10.0:
            raise HTTPException(status_code=400, detail="Maximum bid is 10.0 JOD")
        # SECURITY: Lock user row to prevent race condition on balance check
        user = db.query(models.User).filter(models.User.id == current_user.id).with_for_update().first()
        if float(user.wallet_balance or 0) < 0.07:
            raise HTTPException(status_code=402, detail="Insufficient balance. Minimum 0.07 JOD required.")
        
    ad.cpc_bid = bid_request.cpc_bid
    db.commit()
    db.refresh(ad)
    return ad

ALLOWED_ACTION_TYPES = {"call", "whatsapp", "chat"}

@app.post("/api/ads/{ad_id}/track-click", response_model=dict, dependencies=[Depends(auth.get_rate_limiter(20, 60))])
def track_ad_click(
    ad_id: int, 
    request: Request,
    action_type: str = Body(..., embed=True), # 'call', 'whatsapp', 'chat'
    current_user: Optional[models.User] = Depends(auth.get_current_user_optional),
    db: Session = Depends(get_db)
):
    # SECURITY: Validate action_type to prevent injection
    if action_type not in ALLOWED_ACTION_TYPES:
        raise HTTPException(status_code=400, detail="Invalid action type")
    
    ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
        
    if current_user and current_user.id == ad.user_id:
        return {"status": "success", "deducted": 0.0, "reason": "self_click"}
        
    # Check if this ad has an active bid and the owner has balance
    owner = db.query(models.User).filter(models.User.id == ad.user_id).with_for_update().first()
    if ad.cpc_bid > 0 and owner.wallet_balance >= ad.cpc_bid:
        
        # Click Fraud Protection
        ip_address = auth.get_real_ip(request)
        one_day_ago = datetime.utcnow() - timedelta(days=1)
        
        query = db.query(models.AdClickTracking).filter(
            models.AdClickTracking.ad_id == ad_id,
            models.AdClickTracking.created_at >= one_day_ago
        )
        
        if current_user:
            query = query.filter(
                (models.AdClickTracking.user_id == current_user.id) | 
                (models.AdClickTracking.ip_address == ip_address)
            )
        else:
            query = query.filter(models.AdClickTracking.ip_address == ip_address)
            
        previous_click = query.first()
        
        if previous_click:
            return {"status": "success", "deducted": 0.0, "reason": "duplicate_click_within_24h"}
            
        # Record new click
        click_log = models.AdClickTracking(
            ad_id=ad_id,
            user_id=current_user.id if current_user else None,
            ip_address=ip_address
        )
        db.add(click_log)
        
        from auth import redis_client
        if redis_client:
            try:
                redis_client.hincrby("ad_views_buffer", str(ad_id), 1)
            except Exception as e:
                print(f"Redis error during track_ad_click, triggering fallback: {e}")
                from sqlalchemy import func
                db.query(models.Ad).filter(models.Ad.id == ad_id).update({
                    "views": func.coalesce(models.Ad.views, 0) + 1
                }, synchronize_session=False)
        else:
            # Fallback to direct DB update
            from sqlalchemy import func
            db.query(models.Ad).filter(models.Ad.id == ad_id).update({
                "views": func.coalesce(models.Ad.views, 0) + 1
            }, synchronize_session=False)
        
        # Deduct the bid amount
        owner.wallet_balance = float(owner.wallet_balance) - float(ad.cpc_bid)
        if owner.wallet_balance < 0.07:
            db.query(models.Ad).filter(models.Ad.user_id == owner.id, models.Ad.cpc_bid > 0).update({"cpc_bid": 0.0}, synchronize_session=False)
        
        # SECURITY: Sanitize ad title in transaction description (truncate, no raw user input)
        safe_title = (ad.title or "")[:50].replace("'", "").replace('"', '')
        
        # Log the transaction
        transaction = models.WalletTransaction(
            user_id=owner.id,
            amount=-float(ad.cpc_bid),
            transaction_type="CLICK_DEDUCTION",
            description=f"Action: {action_type} on Ad #{ad.id} '{safe_title}'",
            reference_id=str(ad.id)
        )
        db.add(transaction)
        db.commit()
        return {"status": "success", "deducted": float(ad.cpc_bid)}
        
    return {"status": "success", "deducted": 0.0}

@app.delete("/api/ads/{ad_id}")
def delete_ad(
    ad_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    db_ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not db_ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    if db_ad.user_id != current_user.id and current_user.user_type != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete this ad")
    
    # Explicitly delete child records to prevent foreign key constraint IntegrityError
    # (in case the database is missing ON DELETE CASCADE on these tables)
    db.query(models.AdRealEstateDetail).filter(models.AdRealEstateDetail.ad_id == db_ad.id).delete()
    db.query(models.AdSearchIndex).filter(models.AdSearchIndex.ad_id == db_ad.id).delete()
    db.query(models.SavedAd).filter(models.SavedAd.ad_id == db_ad.id).delete()
    db.query(models.AdReport).filter(models.AdReport.ad_id == db_ad.id).delete()
    db.query(models.AdClickTracking).filter(models.AdClickTracking.ad_id == db_ad.id).delete()
    
    db.delete(db_ad)
    db.commit()
    return {"message": "Ad deleted successfully"}

@app.put("/api/ads/{ad_id}/toggle-featured", response_model=schemas.Ad)
def toggle_featured_ad(
    ad_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    db_ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not db_ad:
        raise HTTPException(status_code=404, detail="Ad not found")
        
    # SECURITY: Only admins can manually toggle featured status
    if current_user.user_type != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to feature ads")
    
    # Fallback to false if it was null
    current_featured = db_ad.is_featured if db_ad.is_featured is not None else False
    db_ad.is_featured = not current_featured
    
    db.commit()
    db.refresh(db_ad)
    return db_ad

@app.put("/api/ads/{ad_id}/toggle-hot", response_model=schemas.Ad)
def toggle_hot_ad(
    ad_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    db_ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not db_ad:
        raise HTTPException(status_code=404, detail="Ad not found")
        
    # SECURITY: Only admins can manually toggle hot status
    if current_user.user_type != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to mark ads as hot")
    
    # Fallback to false if it was null
    current_hot = db_ad.is_hot if db_ad.is_hot is not None else False
    db_ad.is_hot = not current_hot
    
    db.commit()
    db.refresh(db_ad)
    return db_ad

@app.put("/api/ads/{ad_id}/toggle-publish", response_model=schemas.Ad)
def toggle_publish_ad(
    ad_id: int,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    db_ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not db_ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    if db_ad.user_id != current_user.id and current_user.user_type != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to modify this ad")
    
    if not db_ad.is_published:
        if len(image_urls) < 0:
            raise HTTPException(
                status_code=400,
                detail="لابد من رفع 3 صور على الأقل لنشر الإعلان"
            )
            
    db_ad.is_published = not db_ad.is_published
    db.commit()
    db.refresh(db_ad)

    # Notify: Ad publish/unpublish status change to the owner
    if db_ad.is_published:
        background_tasks.add_task(
            send_personal_notification,
            target_user_id=db_ad.user_id,
            title="إعلانك الآن مرئي للجميع 🟢",
            body=f"'{db_ad.title[:50]}' تم نشره وأصبح متاحاً للمستخدمين.",
            notification_type="ad_published",
            reference_id=db_ad.id
        )
    else:
        background_tasks.add_task(
            send_personal_notification,
            target_user_id=db_ad.user_id,
            title="تم إيقاف إعلانك 🔴",
            body=f"'{db_ad.title[:50]}' لم يعد مرئياً للمستخدمين.",
            notification_type="ad_unpublished",
            reference_id=db_ad.id
        )

    return db_ad

@app.put("/api/ads/{ad_id}/toggle-featured", response_model=schemas.Ad)
def toggle_featured_ad(
    ad_id: int,
    current_admin: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    db_ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not db_ad:
        raise HTTPException(status_code=404, detail="Ad not found")
            
    db_ad.is_hot = not db_ad.is_hot
    db.commit()
    db.refresh(db_ad)

    return db_ad

@app.post("/api/ads/{ad_id}/republish", response_model=schemas.Ad)
def republish_ad(ad_id: int, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    db_ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not db_ad:
        raise HTTPException(status_code=404, detail="Ad not found")
        
    if db_ad.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to republish this ad")
        
    last_date = db_ad.last_republished_at or db_ad.created_at
    if last_date and datetime.utcnow() - last_date < timedelta(hours=24):
        raise HTTPException(status_code=400, detail="already_republished")
        
    db_ad.created_at = datetime.utcnow()
    db_ad.last_republished_at = datetime.utcnow()
    db_ad.republish_notification_sent = False
    
    db.commit()
    db.refresh(db_ad)
    
    # Sync back to search index
    SearchService.sync_ad_to_search_index(db, db_ad)
    
    return db_ad

# ============================================================
# User-to-User Interactions & Notifications
# ============================================================

@app.post("/api/ads/{ad_id}/interaction/phone", dependencies=[Depends(auth.get_rate_limiter(30, 60))])
def notify_phone_revealed(
    ad_id: int, 
    background_tasks: BackgroundTasks, 
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Called when a user clicks 'Show Number' on an ad."""
    db_ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not db_ad:
        raise HTTPException(status_code=404, detail="Ad not found")
        
    # Don't notify if the user is viewing their own phone number
    if db_ad.user_id != current_user.id:
        # Prevent spamming: only send once per user per ad per hour/day (simple implementation just sends)
        background_tasks.add_task(
            send_personal_notification,
            target_user_id=db_ad.user_id,
            title="قام أحد المستخدمين بإظهار رقمك 📞",
            body=f"قام أحدهم بإظهار رقم هاتفك في إعلان '{db_ad.title[:30]}'",
            notification_type="phone_revealed",
            reference_id=ad_id
        )
        
    db_ad.chats_count = (db_ad.chats_count or 0) + 1
    db.commit()
    
    return {"status": "success"}

@app.post("/api/ads/{ad_id}/interaction/chat", dependencies=[Depends(auth.get_rate_limiter(30, 60))])
def notify_chat_started(
    ad_id: int, 
    background_tasks: BackgroundTasks, 
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Called when a user clicks 'Chat' or 'WhatsApp' on an ad."""
    db_ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not db_ad:
        raise HTTPException(status_code=404, detail="Ad not found")
        
    if db_ad.user_id != current_user.id:
        background_tasks.add_task(
            send_personal_notification,
            target_user_id=db_ad.user_id,
            title="رسالة محتملة جديدة 💬",
            body=f"مستخدم مهتم بإعلانك '{db_ad.title[:30]}' وانتقل للمحادثة.",
            notification_type="chat_started",
            reference_id=ad_id
        )
        
    db_ad.chats_count = (db_ad.chats_count or 0) + 1
    db.commit()
    
    return {"status": "success"}

from sqlalchemy.dialects.postgresql import insert as pg_insert

@app.post("/api/ads/{ad_id}/interaction/view", dependencies=[Depends(auth.get_rate_limiter(30, 60))])
def record_ad_view(
    ad_id: int, 
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Logs an ad view per user for the history tracking and deducts CPC balance if applicable."""
    # Ensure ad exists
    db_ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not db_ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    db_ad.views = (db_ad.views or 0) + 1

    # Use raw insert / update on conflict for tracking view_at
    stmt = pg_insert(models.user_viewed_ads).values(
        user_id=current_user.id,
        ad_id=ad_id,
        viewed_at=func.now()
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=['user_id', 'ad_id'],
        set_=dict(viewed_at=func.now())
    )
    db.execute(stmt)
    
    db.commit()
    
    milestones = [10, 50, 100, 500, 1000]
    if db_ad.views in milestones:
        background_tasks.add_task(
            send_personal_notification,
            target_user_id=db_ad.user_id,
            title="تهانينا! إعلانك يحقق مشاهدات عالية 🎉",
            body=f"وصل إعلانك '{db_ad.title[:30]}' إلى {db_ad.views} مشاهدة!",
            notification_type="ad_milestone",
            reference_id=ad_id
        )
        
    return {"status": "success"}

@app.post("/api/ads/interactions/bulk-views")
def record_bulk_ad_views(
    request: schemas.BulkViewsRequest,
    current_user: Optional[models.User] = Depends(auth.get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Called by the frontend every few seconds to record impressions (views).
    This buffers the views in Redis to prevent database thrashing.
    """
    from auth import redis_client
    if not redis_client:
        _fallback_bulk_views(db, request.ad_ids)
        return {"status": "success", "fallback": True}
        
    try:
        for ad_id in request.ad_ids:
            redis_client.hincrby("ad_views_buffer", str(ad_id), 1)
        print(f"[DEBUG] Received bulk views from frontend for ads: {request.ad_ids}")
    except Exception as e:
        print(f"Redis error during bulk-views, triggering fallback: {e}")
        _fallback_bulk_views(db, request.ad_ids)
        return {"status": "success", "fallback": True}
        
    return {"status": "success"}

def _fallback_bulk_views(db: Session, ad_ids: list[int]):
    from sqlalchemy import update, func
    try:
        db.execute(update(models.Ad).where(models.Ad.id.in_(ad_ids)).values(
            views=func.coalesce(models.Ad.views, 0) + 1
        ))
        db.commit()
        print(f"[DEBUG] Fallback updated views directly in DB for ads: {ad_ids}")
    except Exception as e:
        db.rollback()
        print(f"Error in fallback ad views update: {e}")

@app.get("/api/my-ads/recently-viewed", response_model=List[schemas.Ad])
def read_recently_viewed_ads(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch the latest 20 ads viewed chronologically by the user."""
    # Join Ads with user_viewed_ads, sort by viewed_at DESC
    from sqlalchemy.orm import selectinload
    
    query = db.query(models.Ad).join(
        models.user_viewed_ads, 
        models.Ad.id == models.user_viewed_ads.c.ad_id
    ).filter(
        models.user_viewed_ads.c.user_id == current_user.id
    ).order_by(
        models.user_viewed_ads.c.viewed_at.desc()
    ).options(
        selectinload(models.Ad.linked_tags),
        selectinload(models.Ad.real_estate_detail)
    ).limit(20)

    return query.all()

from sqlalchemy.orm import Session, joinedload

@app.get("/api/ticker", response_model=List[schemas.LiveTicker])
def read_ticker(db: Session = Depends(get_db)):
    # Fetch latest 5 ticker messages
    tickers = db.query(models.LiveTicker).order_by(models.LiveTicker.created_at.desc()).limit(5).all()
    return tickers

@app.get("/api/stories", response_model=List[schemas.Story])
def read_stories(db: Session = Depends(get_db)):
    stories = db.query(models.Story).options(joinedload(models.Story.owner)).order_by(models.Story.created_at.desc()).limit(20).all()
    return stories


# --- Saved Groups Admin API ---

@app.get("/api/saved-groups", response_model=List[schemas.SavedGroup])
def read_saved_groups(db: Session = Depends(get_db)):
    return db.query(models.SavedGroup).all()

@app.post("/api/saved-groups", response_model=schemas.SavedGroup)
def create_saved_group(group: schemas.SavedGroupCreate, db: Session = Depends(get_db), current_admin: models.User = Depends(auth.get_current_admin)):
    db_group = models.SavedGroup(**group.model_dump())
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

@app.delete("/api/saved-groups/{group_id}")
def delete_saved_group(group_id: int, db: Session = Depends(get_db), current_admin: models.User = Depends(auth.get_current_admin)):
    db_group = db.query(models.SavedGroup).filter(models.SavedGroup.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    db.delete(db_group)
    db.commit()
    return {"message": "Deleted successfully"}

import random

def _enrich_user_profile(user: models.User, db: Session) -> models.User:
    total_ads = db.query(models.Ad).filter(models.Ad.user_id == user.id).count()
    active_ads = db.query(models.Ad).filter(
        models.Ad.user_id == user.id,
        models.Ad.is_published == True,
        models.Ad.is_paused == False,
        models.Ad.is_sold == False,
        models.Ad.is_rejected == False
    ).count()
    
    user.total_ads_count = total_ads
    user.active_ads_count = active_ads
    
    # User requested dummy data for sold ads
    # Assign a dummy random value for demonstration
    user.sold_ads_count = random.randint(3, 12) if total_ads > 0 else 0
    
    return user

class RecentSearchRequest(BaseModel):
    query: str

@app.get("/api/users/me/recent-searches", response_model=List[str])
def get_recent_searches(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    searches = db.query(models.UserRecentSearch).filter(
        models.UserRecentSearch.user_id == current_user.id
    ).order_by(models.UserRecentSearch.created_at.desc()).limit(10).all()
    return [s.query_text for s in searches]

@app.post("/api/users/me/recent-searches")
def save_recent_search(request: RecentSearchRequest, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    query_text = request.query.strip()
    if not query_text:
        return {"status": "ignored"}
    
    existing = db.query(models.UserRecentSearch).filter(
        models.UserRecentSearch.user_id == current_user.id,
        models.UserRecentSearch.query_text == query_text
    ).first()
    
    if existing:
        existing.created_at = func.now()
    else:
        new_search = models.UserRecentSearch(user_id=current_user.id, query_text=query_text)
        db.add(new_search)
        
    # Optional: cleanup if > 10
    total = db.query(models.UserRecentSearch).filter(models.UserRecentSearch.user_id == current_user.id).count()
    if total > 10:
        oldest = db.query(models.UserRecentSearch).filter(models.UserRecentSearch.user_id == current_user.id).order_by(models.UserRecentSearch.created_at.asc()).first()
        if oldest:
            db.delete(oldest)
            
    db.commit()
    return {"status": "success"}

@app.delete("/api/users/me/recent-searches")
def clear_recent_searches(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    db.query(models.UserRecentSearch).filter(models.UserRecentSearch.user_id == current_user.id).delete()
    db.commit()
    return {"status": "success"}

@app.delete("/api/users/me/recent-searches/{query_text}")
def delete_recent_search(query_text: str, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    db.query(models.UserRecentSearch).filter(
        models.UserRecentSearch.user_id == current_user.id,
        models.UserRecentSearch.query_text == query_text
    ).delete()
    db.commit()
    return {"status": "success"}

@app.get("/api/users/me/profile", response_model=schemas.User)
def get_my_profile(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    return _enrich_user_profile(current_user, db)

@app.patch("/api/users/me/profile", response_model=schemas.User)
def update_my_profile(update_data: schemas.UserUpdate, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    if update_data.username is not None:
        current_user.username = update_data.username
    if update_data.full_name is not None:
        current_user.full_name = update_data.full_name
    if update_data.bio is not None:
        current_user.bio = update_data.bio
    if update_data.preferred_contact is not None:
        current_user.preferred_contact = update_data.preferred_contact
    if update_data.languages_spoken is not None:
        current_user.languages_spoken = update_data.languages_spoken
    if update_data.avatar_url is not None:
        current_user.avatar_url = update_data.avatar_url
    if update_data.cover_image_url is not None:
        current_user.cover_image_url = update_data.cover_image_url
    # NOTE: user_type is intentionally NOT settable here — use admin endpoints only
        
    db.commit()
    db.refresh(current_user)
    return _enrich_user_profile(current_user, db)

class LatestCategoryUpdate(BaseModel):
    category_id: int

@app.post("/api/users/me/latest-category")
def update_latest_category(
    payload: LatestCategoryUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    current_user.latest_category_id = payload.category_id
    db.commit()
    return {"status": "success", "latest_category_id": current_user.latest_category_id}

@app.post("/api/users/me/category-filters/{category_id}")
def update_category_filters(
    category_id: int,
    payload: schemas.CategoryFiltersPrefs,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    prefs = current_user.category_filters_prefs or {}
    # Convert payload to dict, remove None values
    payload_dict = payload.dict(exclude_none=True)
    prefs[str(category_id)] = payload_dict
    
    current_user.category_filters_prefs = prefs
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(current_user, "category_filters_prefs")
    db.commit()
    return {"status": "success"}

@app.get("/api/users/me/category-filters/{category_id}", response_model=schemas.CategoryFiltersPrefs)
def get_category_filters(
    category_id: int,
    current_user: models.User = Depends(auth.get_current_user)
):
    prefs = current_user.category_filters_prefs or {}
    category_prefs = prefs.get(str(category_id), {})
    return category_prefs

@app.get("/api/users/{user_id}/profile", response_model=schemas.UserPublicProfile)
def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _enrich_user_profile(user, db)

@app.get("/api/users/{user_id}/reviews", response_model=List[schemas.UserReview])
def get_user_reviews(user_id: int, db: Session = Depends(get_db)):
    reviews = db.query(models.UserReview).filter(models.UserReview.target_user_id == user_id).all()
    return reviews


# The full startup event with DB migrations is at the bottom of this file.


# ---------------------------------------------------------
# AD REPORTING ENDPOINTS
# ---------------------------------------------------------
@app.post("/api/ads/{ad_id}/report")
def report_ad(
    ad_id: int, 
    report: schemas.AdReportCreate,
    current_user: models.User = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
        
    user_id = current_user.id if current_user else None
    
    new_report = models.AdReport(
        ad_id=ad_id,
        user_id=user_id,
        reason=report.reason,
        comments=report.comments
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    return {"status": "success", "message": "Report submitted successfully"}

@app.get("/api/dashboard/reports", response_model=List[schemas.AdReportOut])
def get_dashboard_reports(
    admin_user: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    reports = db.query(models.AdReport).order_by(models.AdReport.created_at.desc()).all()
    
    # Enrich with ad title and reporter name
    result = []
    for r in reports:
        out = schemas.AdReportOut.model_validate(r)
        if r.ad:
            out.ad_title = r.ad.title
        if r.user:
            out.reporter_name = r.user.full_name or r.user.username
            out.reporter_phone = r.user.mobile_number
        result.append(out)
        
    return result


# --- Saved Filter Endpoints ---

@app.post("/api/saved_filters/sync", response_model=List[schemas.SavedFilterResponse])
def sync_saved_filters(
    filters: List[schemas.SavedFilterCreate],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Syncs the local SharedPreferences saved searches to the backend.
    Replaces existing filters for the user to maintain perfect sync.
    """
    # Delete old filters
    db.query(models.SavedFilter).filter(models.SavedFilter.user_id == current_user.id).delete()
    
    # Insert new ones
    db_filters = []
    for f in filters:
        db_filter = models.SavedFilter(**f.dict(), user_id=current_user.id)
        db.add(db_filter)
        db_filters.append(db_filter)
    
    db.commit()
    
    # Refresh to get IDs
    for f in db_filters:
        db.refresh(f)
        
    return db_filters

@app.post("/api/saved_filters", response_model=schemas.SavedFilterResponse)
def create_saved_filter(
    filter_data: schemas.SavedFilterCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    db_filter = models.SavedFilter(**filter_data.dict(), user_id=current_user.id)
    db.add(db_filter)
    db.commit()
    db.refresh(db_filter)
    return db_filter

@app.get("/api/saved_filters", response_model=List[schemas.SavedFilterResponse])
def get_saved_filters(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    filters = db.query(models.SavedFilter).filter(models.SavedFilter.user_id == current_user.id).all()
    return filters


@app.delete("/api/saved_filters/{filter_id}")
def delete_saved_filter(
    filter_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    db_filter = db.query(models.SavedFilter).filter(
        models.SavedFilter.id == filter_id,
        models.SavedFilter.user_id == current_user.id
    ).first()
    
    if not db_filter:
        raise HTTPException(status_code=404, detail="Filter not found")
        
    db.delete(db_filter)
    db.commit()
    return {"status": "success"}

@app.get("/api/ads/{ad_id}", response_model=schemas.Ad)
def get_ad_by_id(ad_id: int, db: Session = Depends(get_db)):
    ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    return ad

import asyncio
from datetime import datetime, timedelta

async def republish_notifier_worker():
    while True:
        try:
            from database import SessionLocal
            from notifications import send_personal_notification
            db = SessionLocal()
            from sqlalchemy import or_, update
            
            now_minus_24h = datetime.utcnow() - timedelta(hours=24)
            
            # Use an atomic UPDATE with RETURNING to claim the ads exclusively for this worker
            stmt = (
                update(models.Ad)
                .where(
                    models.Ad.is_sold == False,
                    models.Ad.is_published == True,
                    models.Ad.republish_notification_sent == False,
                    or_(
                        models.Ad.last_republished_at <= now_minus_24h,
                        (models.Ad.last_republished_at == None) & (models.Ad.created_at <= now_minus_24h)
                    )
                )
                .values(republish_notification_sent=True)
                .returning(
                    models.Ad.id, 
                    models.Ad.user_id, 
                    models.Ad.title, 
                    models.Ad.views, 
                    models.Ad.chats_count
                )
            )
            
            # fetchall() executes the statement and retrieves the rows updated by THIS specific worker
            result = db.execute(stmt)
            try:
                updated_ads = result.fetchall()
            except Exception:
                updated_ads = []
            db.commit()
            
            if updated_ads:
                user_ads = {}
                for ad in updated_ads:
                    user_ads.setdefault(ad.user_id, []).append(ad)
                    
                for user_id, u_ads in user_ads.items():
                    if len(u_ads) == 1:
                        ad = u_ads[0]
                        await send_personal_notification(
                            target_user_id=user_id,
                            title="إحصائيات إعلانك 📊",
                            body=f"حصل إعلانك '{ad.title}' على {ad.views} مشاهدة و {ad.chats_count} محادثة! يمكنك إعادة نشره الآن ليظهر في الأعلى.",
                            notification_type="republish_available",
                            reference_id=ad.id
                        )
                    else:
                        await send_personal_notification(
                            target_user_id=user_id,
                            title="إعلانات جاهزة لإعادة النشر 🚀",
                            body=f"لديك {len(u_ads)} إعلانات جاهزة لإعادة النشر الآن لترتفع إلى أعلى القائمة! اضغط هنا لإعادة نشرها.",
                            notification_type="republish_available",
                            reference_id=None
                        )
        except Exception as e:
            print(f"Error in republish_notifier_worker: {e}")
        finally:
            if 'db' in locals(): 
                try:
                    db.close()
                except Exception:
                    pass
        await asyncio.sleep(600)

async def facebook_autopost_worker():
    while True:
        try:
            from database import SessionLocal
            from facebook_publisher import publish_facebook_post
            from sqlalchemy import func
            
            
            db = SessionLocal()
            
            # Fetch rules from DB
            rules = db.query(models.FacebookAutoPostRule).all()
            rules_dict = {rule.region_name: rule.threshold for rule in rules}
            
            if not rules_dict:
                db.close()
                await asyncio.sleep(1800)
                continue
                
            # Find combinations of location and category with >= 50 unsent ads
            region_counts = db.query(
                models.Ad.location, 
                models.Ad.category_id,
                func.count(models.Ad.id).label('ad_count')
            ).filter(
                models.Ad.is_facebook_posted == False,
                models.Ad.location != None,
                models.Ad.category_id != None
            ).group_by(models.Ad.location, models.Ad.category_id).having(func.count(models.Ad.id) >= 50).all()
            
            import json
            import urllib.parse
            
            for location, category_id, count in region_counts:
                # Get the latest 15 ads for this combination
                ads = db.query(models.Ad).filter(
                    models.Ad.is_facebook_posted == False,
                    models.Ad.location == location,
                    models.Ad.category_id == category_id
                ).order_by(models.Ad.created_at.desc()).limit(15).all()
                
                if not ads:
                    continue
                    
                # Atomically claim these ads to prevent duplicate posting by other workers
                from sqlalchemy import update
                ad_ids = [a.id for a in ads]
                stmt = (
                    update(models.Ad)
                    .where(models.Ad.id.in_(ad_ids), models.Ad.is_facebook_posted == False)
                    .values(is_facebook_posted=True)
                )
                res = db.execute(stmt)
                db.commit()
                
                if res.rowcount == 0:
                    continue # Another worker already claimed and processed these
                    
                category = db.query(models.Category).filter(models.Category.id == category_id).first()
                category_name = category.name if category else "عقار"
                
                categoryHashtag = category_name.replace(" ", "_")
                regionHashtag = location.replace(" ", "_") if location else "الاردن"
                hashtags = f"#{categoryHashtag} #{regionHashtag} #عقارات #عقارات_الاردن #سوقكم"
                
                msg = f"تبحث عن {category_name} في {location}؟ 🏡✨\nاكتشف أحدث وأفضل {category_name} المعروضة لدينا في هذه المجموعة المميزة! 🌟\n\n"
                
                for i, ad in enumerate(ads, 1):
                    price_str = f"{ad.price} دينار" if ad.price else "تواصل لمعرفة السعر"
                    title = ad.title[:50] + "..." if ad.title and len(ad.title) > 50 else (ad.title or "عقار")
                    msg += f"{i}. {title}\n💰 السعر: {price_str}\n🔗 التفاصيل: https://share.sooq-com.com/ad/{ad.id}\n\n"
                
                msg += "تصفح المزيد على تطبيق وموقع سوقكم! ✨\n\n"
                msg += hashtags
                
                main_link = f"https://share.sooq-com.com/ad/{ads[0].id}"
                
                child_attachments = []
                for ad in ads:
                    main_image = None
                    if hasattr(ad, 'image_urls') and ad.image_urls:
                        main_image = ad.image_urls[0] if ad.image_urls else None
                    elif hasattr(ad, 'image_url') and ad.image_url:
                        try:
                            parsed = json.loads(ad.image_url)
                            if isinstance(parsed, list) and parsed:
                                main_image = parsed[0]
                            else:
                                main_image = ad.image_url
                        except:
                            main_image = ad.image_url
                            
                    if main_image and isinstance(main_image, str):
                        price_str = f"{ad.price} دينار" if ad.price else "تواصل لمعرفة السعر"
                        title = ad.title[:30] + "..." if ad.title and len(ad.title) > 30 else (ad.title or "عقار")
                        child_attachments.append({
                            "link": f"https://share.sooq-com.com/ad/{ad.id}",
                            "name": title,
                            "description": price_str,
                            "picture": main_image
                        })
                        
                child_attachments = child_attachments[:10]
                
                success = await publish_facebook_post(msg, main_link, child_attachments=child_attachments)
                if not success:
                    # Revert the claim if FB posting failed
                    db.execute(update(models.Ad).where(models.Ad.id.in_(ad_ids)).values(is_facebook_posted=False))
                    db.commit()
        except Exception as e:
            print(f"Error in facebook_autopost_worker: {e}")
        finally:
            if 'db' in locals(): 
                try:
                    db.close()
                except Exception:
                    pass
        await asyncio.sleep(1800) # Check every 30 minutes

async def sync_ad_views_worker():
    """Periodically fetch aggregated ad views from Redis and bulk update PostgreSQL."""
    from auth import redis_client
    import asyncio
    
    while True:
        try:
            if redis_client and redis_client.exists("ad_views_buffer"):
                # Fetch all buffered views and immediately delete the key to start a new buffer
                pipe = redis_client.pipeline()
                pipe.hgetall("ad_views_buffer")
                pipe.delete("ad_views_buffer")
                results = pipe.execute()
                
                views_data = results[0]
                if views_data:
                    # views_data is a dict like {'1': '5', '12': '1'}
                    db = SessionLocal()
                    try:
                        from sqlalchemy import update, func
                        for ad_id_str, count_str in views_data.items():
                            ad_id = int(ad_id_str)
                            count = int(count_str)
                            if count > 0:
                                db.execute(update(models.Ad).where(models.Ad.id == ad_id).values(
                                    views=func.coalesce(models.Ad.views, 0) + count
                                ))
                        db.commit()
                        print(f"[DEBUG] sync_ad_views_worker successfully updated views for {len(views_data)} ads.")
                    except Exception as e:
                        db.rollback()
                        print(f"Error bulk updating ad views: {e}")
                        # Put them back if it failed to not lose impressions
                        for ad_id_str, count_str in views_data.items():
                            redis_client.hincrby("ad_views_buffer", ad_id_str, int(count_str))
                    finally:
                        db.close()
        except Exception as e:
            print(f"Error in sync_ad_views_worker: {e}")
            
        await asyncio.sleep(60)

from arq import create_pool
from arq.connections import RedisSettings

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(republish_notifier_worker())
    asyncio.create_task(facebook_autopost_worker())
    asyncio.create_task(sync_ad_views_worker())
    
    try:
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_password = os.getenv("REDIS_PASSWORD", None)
        app.state.arq_pool = await create_pool(RedisSettings(
            host=redis_host, 
            port=redis_port, 
            password=redis_password
        ))
    except Exception as e:
        print(f"Failed to connect to ARQ Redis pool: {e}")
        app.state.arq_pool = None
    
    # Run DB Migrations for new tracking columns
    try:
        db = SessionLocal()
        try:
            # Add is_active and is_banned to users
            db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"))
            db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE"))
            
            # Create support_messages table if it doesn't exist
            db.execute(text("""
            CREATE TABLE IF NOT EXISTS support_messages (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                sender VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """))
            # Add latest_category_id to users
            db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS latest_category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL"))
            
            # Add category_filters_prefs to users
            db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS category_filters_prefs JSONB DEFAULT '{}'::jsonb"))
            
            # Add last_notified_ad_count to categories
            db.execute(text("ALTER TABLE categories ADD COLUMN IF NOT EXISTS last_notified_ad_count INTEGER DEFAULT 0"))
            db.commit()
        except Exception as e:
            print(f"Migration error: {e}")
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception as e:
        print(f"Critical error during startup DB migrations: {e}")

def log_search_query_task(search: str, results_count: int, user_id: int, category_id: int = None, tags: list = None):
    if not search or not search.strip():
        return
    from database import SessionLocal
    from models import SearchQueryLog, Category
    db = SessionLocal()
    try:
        category_name = None
        if category_id:
            category = db.query(Category).filter(Category.id == category_id).first()
            if category:
                category_name = category.name_ar
                
        tags_str = ", ".join(tags) if tags else None
        
        log_entry = SearchQueryLog(
            query_text=search.strip(),
            results_count=results_count,
            user_id=user_id,
            category_name=category_name,
            extracted_tags=tags_str
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error logging search in background: {e}")
    finally:
        db.close()

async def check_category_milestone_task(category_id: int):
    # This task opens its own DB session
    db = SessionLocal()
    try:
        cat = db.query(models.Category).filter(models.Category.id == category_id).first()
        if not cat:
            return
            
        total_ads = db.query(models.Ad).filter(
            models.Ad.category_id == category_id,
            models.Ad.is_published == True
        ).count()
        
        if total_ads >= cat.last_notified_ad_count + 100:
            cat.last_notified_ad_count = total_ads
            db.commit()
            
            can_send_global = True
            throttle_key = f"global_milestone_{category_id}"
            try:
                from auth import redis_client, USING_REDIS
                import time
                if USING_REDIS:
                    if redis_client.exists(throttle_key):
                        can_send_global = False
                    else:
                        redis_client.setex(throttle_key, 86400, "1") # 24 hours
                else:
                    global LAST_GLOBAL_MILESTONE
                    if 'LAST_GLOBAL_MILESTONE' not in globals():
                        globals()['LAST_GLOBAL_MILESTONE'] = {}
                    
                    last_time = globals()['LAST_GLOBAL_MILESTONE'].get(throttle_key, 0)
                    if time.time() - last_time < 86400:
                        can_send_global = False
                    else:
                        globals()['LAST_GLOBAL_MILESTONE'][throttle_key] = time.time()
            except Exception:
                pass
                
            if can_send_global:
                try:
                    import firebase_admin
                    from firebase_admin import messaging
                    from notifications import init_firebase_admin
                    if init_firebase_admin() and firebase_admin._apps:
                        message = messaging.Message(
                            notification=messaging.Notification(
                                title="إعلانات جديدة 🚀", 
                                body=f"أكثر من 100 إعلان جديد في قسم {cat.name}! تصفحها الآن"
                            ),
                            android=messaging.AndroidConfig(
                                priority="high",
                                notification=messaging.AndroidNotification(channel_id="high_importance_channel", sound="default")
                            ),
                            data={"type": "category_milestone", "category_id": str(category_id)},
                            topic="all_users",
                        )
                        messaging.send(message)
                        print(f"[FCM] Global milestone push sent for category {category_id}")
                except Exception as e:
                    print(f"Error sending global topic milestone notification: {e}")
    finally:
        db.close()


class AppConfigUpdate(BaseModel):
    latest_version: str
    min_required_version: str
    store_url_android: str
    store_url_ios: str

@app.get("/api/config/version")
def get_version_config(db: Session = Depends(get_db)):
    config = db.query(models.AppConfig).first()
    if not config:
        return {
            "latest_ios": "1.0.5",
            "min_ios": "1.0.0",
            "testflight_url": "https://testflight.apple.com/join/W73QoHhW"
        }
    return {
        "latest_version": config.latest_version,
        "min_required_version": config.min_required_version,
        "store_url_android": config.store_url_android,
        "store_url_ios": config.store_url_ios
    }

@app.put("/api/config/version")
def update_version_config(req: AppConfigUpdate, current_admin: models.User = Depends(auth.get_current_admin), db: Session = Depends(get_db)):
    config = db.query(models.AppConfig).first()
    if not config:
        config = models.AppConfig(**req.dict())
        db.add(config)
    else:
        config.latest_version = req.latest_version
        config.min_required_version = req.min_required_version
        config.store_url_android = req.store_url_android
        config.store_url_ios = req.store_url_ios
    db.commit()
    db.refresh(config)
    return {"status": "success", "config": req.dict()}

# Trigger reload

# Trigger reload 2
