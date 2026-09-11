from sqlalchemy import Column, Integer, String, Text, DECIMAL, ForeignKey, TIMESTAMP, Boolean, Enum, Table, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from database import Base
import enum

# Association Tables for Many-to-Many Relationships
category_tags = Table(
    'category_tags',
    Base.metadata,
    Column('category_id', Integer, ForeignKey('categories.id', ondelete="CASCADE"), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id', ondelete="CASCADE"), primary_key=True)
)

ad_tags = Table(
    'ad_tags',
    Base.metadata,
    Column('ad_id', Integer, ForeignKey('ads.id', ondelete="CASCADE"), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id', ondelete="CASCADE"), primary_key=True)
)

user_viewed_ads = Table(
    'user_viewed_ads',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete="CASCADE"), primary_key=True),
    Column('ad_id', Integer, ForeignKey('ads.id', ondelete="CASCADE"), primary_key=True),
    Column('viewed_at', TIMESTAMP, server_default=func.now(), onupdate=func.now())
)

class City(Base):
    __tablename__ = "cities"
    id = Column(Integer, primary_key=True, index=True)
    name_ar = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=False)
    
    regions = relationship("Region", back_populates="city")

class Region(Base):
    __tablename__ = "regions"
    id = Column(Integer, primary_key=True, index=True)
    city_id = Column(Integer, ForeignKey("cities.id", ondelete="CASCADE"), nullable=False)
    name_ar = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=False)
    latitude = Column(DECIMAL(10, 8), nullable=True)
    longitude = Column(DECIMAL(11, 8), nullable=True)
    
    __table_args__ = (UniqueConstraint('city_id', 'name_ar', name='uq_region_city_name_ar'),)
    
    city = relationship("City", back_populates="regions")
    aliases = relationship("RegionAlias", back_populates="region", cascade="all, delete-orphan")

class RegionAlias(Base):
    __tablename__ = "region_aliases"
    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id", ondelete="CASCADE"), nullable=False)
    alias_name = Column(String(100), nullable=False, unique=True)
    
    region = relationship("Region", back_populates="aliases")

class Directorate(Base):
    __tablename__ = "directorates"
    id = Column(Integer, primary_key=True, index=True)
    city_id = Column(Integer, ForeignKey("cities.id", ondelete="CASCADE"), nullable=False)
    name_ar = Column(String(100), nullable=False)

class Village(Base):
    __tablename__ = "villages"
    id = Column(Integer, primary_key=True, index=True)
    directorate_id = Column(Integer, ForeignKey("directorates.id", ondelete="CASCADE"), nullable=False)
    name_ar = Column(String(100), nullable=False)

class Basin(Base):
    __tablename__ = "basins"
    id = Column(Integer, primary_key=True, index=True)
    village_id = Column(Integer, ForeignKey("villages.id", ondelete="CASCADE"), nullable=False)
    name_ar = Column(String(100), nullable=False)

class NeighborhoodSector(Base):
    __tablename__ = "neighborhood_sectors"
    id = Column(Integer, primary_key=True, index=True)
    basin_id = Column(Integer, ForeignKey("basins.id", ondelete="CASCADE"), nullable=False)
    name_ar = Column(String(100), nullable=False)
class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    
    # Relationships
    categories = relationship("Category", secondary=category_tags, back_populates="linked_tags")
    ads = relationship("Ad", secondary=ad_tags, back_populates="linked_tags")

class SourceType(str, enum.Enum):
    ORGANIC_USER = "ORGANIC_USER"
    SCRAPER_BOT = "SCRAPER_BOT"
    SCRAPER = "SCRAPER"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    mobile_number = Column(String(20), unique=True, index=True, nullable=True) # Mobile OTP priority
    username = Column(String(50), unique=True, nullable=True) # Optional now
    email = Column(String(100), unique=True, nullable=True) # Optional now
    hashed_password = Column(String(255), nullable=True) # Optional now
    phone = Column(String(20))
    avatar_url = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Profile & Premium Features
    user_type = Column(String(50), default="private")
    cover_image_url = Column(Text, nullable=True)
    overall_rating = Column(DECIMAL(3, 2), default=0.0)
    response_rate = Column(Integer, default=100)
    average_response_time = Column(String(50), default="Typically replies within 1 hour")
    trust_score = Column(Integer, default=50)
    followers_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    is_email_verified = Column(Boolean, default=False)
    is_phone_verified = Column(Boolean, default=False)
    is_identity_verified = Column(Boolean, default=False)
    location = Column(String(100), default="")
    is_active = Column(Boolean, default=True)
    is_banned = Column(Boolean, default=False)
    
    wallet_balance = Column(DECIMAL(10, 2), default=0.00)
    
    # KYC Identity Verification
    full_name = Column(String(100), nullable=True)
    national_id = Column(String(20), nullable=True, unique=True)
    date_of_birth = Column(String(20), nullable=True)
    id_expiry_date = Column(String(20), nullable=True)
    identity_document_url = Column(Text, nullable=True)
    liveness_passed = Column(Boolean, default=False)
    face_similarity_score = Column(DECIMAL(5, 2), nullable=True)
    verification_status = Column(String(20), default="pending") # pending, verified, rejected
    
    # Advanced Profile Ext.
    bio = Column(Text, nullable=True)
    preferred_contact = Column(String(50), nullable=True)
    languages_spoken = Column(JSONB, nullable=True)
    deals_completed = Column(Integer, default=0)
    
    # Anti-Spam & Penalty System
    duplicate_attempts = Column(Integer, default=0)
    first_duplicate_attempt_at = Column(TIMESTAMP, nullable=True)
    banned_from_posting_until = Column(TIMESTAMP, nullable=True)
    penalty_tier = Column(Integer, default=0)
    last_penalty_at = Column(TIMESTAMP, nullable=True)
    cancellation_rate = Column(Integer, default=0)
    buyer_satisfaction = Column(Integer, default=0)
    shop_name = Column(String(100), nullable=True)
    
    # Tracking
    ip_address = Column(String(50), nullable=True)
    business_policy = Column(Text, nullable=True)
    shop_location = Column(Text, nullable=True)
    shop_hours = Column(String(100), nullable=True)
    
    # Category Tracking
    latest_category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    category_filters_prefs = Column(JSONB, default=dict)
    
    ads = relationship("Ad", back_populates="owner")
    metrics = relationship("UserMetric", back_populates="user", uselist=False)
    reviews_received = relationship("UserReview", foreign_keys="UserReview.target_user_id", back_populates="target_user")
    reviews_given = relationship("UserReview", foreign_keys="UserReview.reviewer_id", back_populates="reviewer")
    viewed_ads = relationship("Ad", secondary=user_viewed_ads, back_populates="viewed_by_users")

class SupportMessage(Base):
    __tablename__ = "support_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sender = Column(String(50), nullable=False) # 'user' or 'admin'
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    user = relationship("User")

class UserReview(Base):
    __tablename__ = "user_reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    target_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating = Column(DECIMAL(3, 2), nullable=False)
    text = Column(Text, nullable=False)
    tags = Column(JSONB, default=[]) # Qualitative tags like 'Fast responder'
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    target_user = relationship("User", foreign_keys=[target_user_id], back_populates="reviews_received")
    reviewer = relationship("User", foreign_keys=[reviewer_id], back_populates="reviews_given")

class UserMetric(Base):
    __tablename__ = "user_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    saved_items = Column(Integer, default=0)
    recently_viewed = Column(Integer, default=0)
    active_ads = Column(Integer, default=0)

    user = relationship("User", back_populates="metrics")

class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(DECIMAL(10, 2), nullable=False) # Positive for top-up, negative for deduction
    transaction_type = Column(String(50), nullable=False) # e.g., 'TOPUP', 'CLICK_DEDUCTION'
    description = Column(String(255), nullable=True) # e.g., 'Click on Ad #123'
    reference_id = Column(String(255), nullable=True) # e.g., IAP Receipt ID
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User")

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    icon_name = Column(String(50))
    color_hex = Column(String(10))
    background_url = Column(String(255))
    tag = Column(String(50))
    slugs = Column(JSONB)
    order_index = Column(Integer, default=0)
    last_notified_ad_count = Column(Integer, default=0)

    ads = relationship("Ad", back_populates="category")
    children = relationship("Category", backref="parent", remote_side=[id])
    linked_tags = relationship("Tag", secondary=category_tags, back_populates="categories")

class Ad(Base):
    __tablename__ = "ads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"))
    title = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    raw_description = Column(Text, nullable=True)
    price = Column(DECIMAL(10, 2), nullable=True)
    location = Column(Text, nullable=True)
    image_url = Column(Text)
    attributes = Column(JSONB)
    views = Column(Integer, default=0)
    is_hot = Column(Boolean, default=False)
    is_published = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)
    
    # My Ads / User Listings support fields
    expires_at = Column(TIMESTAMP, nullable=True)
    is_paused = Column(Boolean, default=False)
    is_sold = Column(Boolean, default=False)
    is_rejected = Column(Boolean, default=False)
    rejected_reason = Column(Text, nullable=True)
    is_boosted = Column(Boolean, default=False)
    boost_expiry = Column(TIMESTAMP, nullable=True)
    chats_count = Column(Integer, default=0)
    favorites_count = Column(Integer, default=0)
    
    # Pay-Per-Click Bidding
    cpc_bid = Column(DECIMAL(10, 2), default=0.00)
    
    duplicate_status = Column(String(50), nullable=True)
    highest_duplicate_score = Column(Integer, nullable=True)
    
    last_republished_at = Column(TIMESTAMP, nullable=True)
    republish_notification_sent = Column(Boolean, default=False)
    
    # Scraper Support Fields
    source_type = Column(Enum(SourceType), default=SourceType.ORGANIC_USER)
    source_url = Column(Text, nullable=True, index=True)
    is_facebook_posted = Column(Boolean, default=False)
    primary_image_hash = Column(String(64), nullable=True, index=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    ip_address = Column(String(50), nullable=True)

    owner = relationship("User", back_populates="ads")
    category = relationship("Category", back_populates="ads")
    real_estate_detail = relationship("AdRealEstateDetail", back_populates="ad", uselist=False, cascade="all, delete-orphan")
    linked_tags = relationship("Tag", secondary=ad_tags, back_populates="ads")
    viewed_by_users = relationship("User", secondary=user_viewed_ads, back_populates="viewed_ads")

    @property
    def image_urls(self):
        if self.attributes and isinstance(self.attributes, dict):
            val = self.attributes.get("image_urls")
            return val if val is not None else []
        return []

    @image_urls.setter
    def image_urls(self, value):
        if self.attributes is None:
            self.attributes = {}
        self.attributes = {**self.attributes, "image_urls": value}

    @property
    def video_url(self):
        if self.attributes and isinstance(self.attributes, dict):
            return self.attributes.get("video_url")
        return None

    @video_url.setter
    def video_url(self, value):
        if self.attributes is None:
            self.attributes = {}
        self.attributes = {**self.attributes, "video_url": value}

    @property
    def phone_number(self):
        if self.attributes and isinstance(self.attributes, dict):
            return self.attributes.get("phone_number")
        return None

    @phone_number.setter
    def phone_number(self, value):
        if self.attributes is None:
            self.attributes = {}
        self.attributes = {**self.attributes, "phone_number": value}

    @property
    def rooms(self):
        if self.attributes and isinstance(self.attributes, dict):
            return self.attributes.get("rooms")
        return None

    @rooms.setter
    def rooms(self, value):
        if self.attributes is None:
            self.attributes = {}
        self.attributes = {**self.attributes, "rooms": value}

class AdRealEstateDetail(Base):
    __tablename__ = "ad_real_estate_details"

    id = Column(Integer, primary_key=True, index=True)
    ad_id = Column(Integer, ForeignKey("ads.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    bathrooms = Column(Integer, nullable=True)
    furnished = Column(String(50), nullable=True)
    build_area = Column(Integer, nullable=True)
    floor = Column(String(50), nullable=True)
    building_age = Column(String(50), nullable=True)
    rent_duration = Column(String(50), nullable=True)
    view_orientation = Column(String(50), nullable=True)

    key_features = Column(JSONB, default=[])
    additional_features = Column(JSONB, default=[])
    nearby_locations = Column(JSONB, default=[])

    ad = relationship("Ad", back_populates="real_estate_detail")

class LiveTicker(Base):
    __tablename__ = "live_tickers"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

class Story(Base):
    __tablename__ = "stories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    image_url = Column(Text, nullable=False)
    title = Column(String(100))
    created_at = Column(TIMESTAMP, server_default=func.now())

    owner = relationship("User")

class SavedGroup(Base):
    __tablename__ = "saved_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    url = Column(Text, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    category = relationship("Category")

class OtpCode(Base):
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True, index=True)
    mobile_number = Column(String(20), index=True, nullable=False)
    otp_code = Column(String(10), nullable=False)
    expires_at = Column(TIMESTAMP, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    attempts = Column(Integer, default=0)
    ip_address = Column(String(50))

class RateLimitLog(Base):
    __tablename__ = "rate_limit_logs"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(50), index=True, nullable=True)
    mobile_number = Column(String(20), index=True, nullable=True)
    endpoint = Column(String(100), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    target_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    type = Column(String(50), nullable=True)          # e.g. "new_ad", "message", "system"
    reference_id = Column(Integer, nullable=True)      # e.g. ad_id, message_id
    is_read = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    target_user = relationship("User")

class UserDeviceToken(Base):
    __tablename__ = "user_device_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    fcm_token = Column(Text, nullable=False, unique=True)
    device_type = Column(String(20), nullable=True)    # "android", "ios", "web"
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User")

class UserActivityLog(Base):
    __tablename__ = "user_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    action_type = Column(String(100), nullable=False) # e.g. "APPLY_FILTER", "VIEW_CATEGORY", "SEARCH"
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    filters_json = Column(JSONB, nullable=True) # stores applied filter state
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User")
    category = relationship("Category")

class UserRecentSearch(Base):
    __tablename__ = "user_recent_searches"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    query_text = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("User")


class SavedFilter(Base):
    __tablename__ = "saved_filters"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(100), nullable=True)
    min_price = Column(DECIMAL(10, 2), nullable=True)
    max_price = Column(DECIMAL(10, 2), nullable=True)
    tags = Column(JSONB, nullable=True)      # ["مفروشة", "عمان", ...]
    locations = Column(JSONB, nullable=True) # ["عمان", "صويلح", ...]
    alert_frequency = Column(String(50), default="none") # e.g. "فوري", "يومي", "none"
    search_query = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User")
    category = relationship("Category")

class AITrainingLog(Base):
    __tablename__ = "ai_training_logs"

    id = Column(Integer, primary_key=True, index=True)
    post_text = Column(Text, nullable=False)
    status = Column(String(50), nullable=False) # e.g. success, failed, rejected
    ai_model = Column(String(100), nullable=True) # e.g. gemini-2.5-flash-lite, deepseek-chat
    ai_output = Column(JSONB, nullable=True)     # Stores the parsed dictionary from AI
    raw_response = Column(Text, nullable=True)   # Stores the exact unparsed text returned by AI for training
    reason = Column(Text, nullable=True)         # E.g. "Seeking apartment (category_id=0)"
    created_at = Column(TIMESTAMP, server_default=func.now())

class SavedAd(Base):
    __tablename__ = "saved_ads"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    ad_id = Column(Integer, ForeignKey("ads.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AdReport(Base):
    __tablename__ = "ad_reports"
    id = Column(Integer, primary_key=True, index=True)
    ad_id = Column(Integer, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True) # nullable for anonymous
    reason = Column(String(255), nullable=False)
    comments = Column(Text, nullable=True)
    status = Column(String(50), default="pending") # pending, reviewed, dismissed
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    ad = relationship("Ad", backref="reports")
    user = relationship("User")

class AdSearchIndex(Base):
    __tablename__ = "ad_search_index"
    
    ad_id = Column(Integer, ForeignKey("ads.id", ondelete="CASCADE"), primary_key=True)
    category_id = Column(Integer, nullable=False, index=True)
    city_id = Column(Integer, nullable=True, index=True)
    region_id = Column(Integer, nullable=True, index=True)
    deal_type = Column(String(20), nullable=True) # SALE, RENT, BOTH
    property_type = Column(String(50), nullable=True)
    price = Column(DECIMAL(12, 2), nullable=True)
    bedrooms = Column(Integer, nullable=True)
    bathrooms = Column(Integer, nullable=True)
    furnished = Column(Boolean, nullable=True)
    build_area = Column(DECIMAL(10, 2), nullable=True)
    floor_number = Column(Integer, nullable=True)
    is_hot = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)
    is_boosted = Column(Boolean, default=False)
    attributes_jsonb = Column(JSONB, nullable=True)
    search_text = Column(Text, nullable=True)
    search_vector = Column(TSVECTOR, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    ad = relationship("Ad")

class ScrapingLog(Base):
    __tablename__ = "scraping_logs"

    id = Column(Integer, primary_key=True, index=True)
    group_name = Column(String(255), nullable=True)
    saved_ads = Column(Integer, default=0)
    skipped_ads = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    json_data = Column(JSONB, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), index=True)

class SearchQueryLog(Base):
    __tablename__ = "search_query_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    query_text = Column(String(255), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    results_count = Column(Integer, default=0)
    category_name = Column(String(255), nullable=True)
    extracted_tags = Column(String(500), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), index=True)
    
    user = relationship("User")

class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_name = Column(String(100), nullable=False, index=True)
    user_id = Column(String(100), nullable=True, index=True) # Could be string (device ID) or integer
    screen = Column(String(100), nullable=True)
    metadata_json = Column(JSONB, nullable=True)
    timestamp = Column(TIMESTAMP(timezone=True), server_default=func.now(), index=True)
    ip_address = Column(String(50), nullable=True)

class FacebookAutoPostRule(Base):
    __tablename__ = "facebook_autopost_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    region_name = Column(Text, unique=True, index=True)
    threshold = Column(Integer, default=100)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False)
    expires_at = Column(TIMESTAMP, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    user = relationship("User")

class GeminiUsageLog(Base):
    __tablename__ = "gemini_usage_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), index=True)


class AppConfig(Base):
    __tablename__ = 'app_config'

    id = Column(Integer, primary_key=True, index=True)
    latest_version = Column(String(50), nullable=False, default='1.0.0')
    min_required_version = Column(String(50), nullable=False, default='1.0.0')
    store_url_android = Column(String(500), nullable=True)
    store_url_ios = Column(String(500), nullable=True)


class ApiHitLog(Base):
    __tablename__ = 'api_hit_logs'

    id = Column(Integer, primary_key=True, index=True)
    endpoint_name = Column(String(255), index=True)
    ip_address = Column(String(50), index=True)
    response_time_ms = Column(DECIMAL(10, 2), nullable=True)
    status_code = Column(Integer, nullable=True)
    user_agent = Column(String(500), nullable=True)
    query_params = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship('User')

class BlockedPhoneNumber(Base):
    __tablename__ = 'blocked_phone_numbers'
    phone_number = Column(String(20), primary_key=True, index=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

class AdClickTracking(Base):
    __tablename__ = "ad_click_tracking"

    id = Column(Integer, primary_key=True, index=True)
    ad_id = Column(Integer, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    ip_address = Column(String(50), nullable=True, index=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)
