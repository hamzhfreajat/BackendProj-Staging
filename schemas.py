from pydantic import BaseModel, field_validator
from typing import List, Optional, Any
from datetime import datetime
import math

class BulkViewsRequest(BaseModel):
    ad_ids: List[int]

class WalletTransactionBase(BaseModel):
    amount: float
    transaction_type: str
    description: Optional[str] = None
    reference_id: Optional[str] = None

class WalletTransaction(WalletTransactionBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

ALLOWED_PRODUCT_IDS = {"wallet_topup_10", "wallet_topup_20", "wallet_topup_50"}
ALLOWED_PLATFORMS = {"ios", "android"}

class WalletTopupRequest(BaseModel):
    receipt_data: str
    product_id: str
    platform: str # 'ios' or 'android'

    @field_validator('platform')
    @classmethod
    def validate_platform(cls, v):
        if v.lower() not in ALLOWED_PLATFORMS:
            raise ValueError(f"Platform must be one of: {', '.join(ALLOWED_PLATFORMS)}")
        return v.lower()

    @field_validator('product_id')
    @classmethod
    def validate_product_id(cls, v):
        if v not in ALLOWED_PRODUCT_IDS:
            raise ValueError("Invalid product ID")
        return v

    @field_validator('receipt_data')
    @classmethod
    def validate_receipt_data(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Receipt data cannot be empty")
        if len(v) > 50000:
            raise ValueError("Receipt data exceeds maximum allowed length")
        return v

class AdBidRequest(BaseModel):
    cpc_bid: float

    @field_validator('cpc_bid')
    @classmethod
    def validate_cpc_bid(cls, v):
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Bid must be a valid number")
        if v < 0:
            raise ValueError("Bid cannot be negative")
        if v > 0 and v < 0.07:
            raise ValueError("Minimum bid is 0.07 JOD")
        if v > 10.0:
            raise ValueError("Maximum bid is 10.0 JOD")
        return round(v, 2)



class UserBase(BaseModel):
    mobile_number: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    full_name: Optional[str] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    bio: Optional[str] = None
    preferred_contact: Optional[str] = None
    languages_spoken: Optional[List[str]] = None
    avatar_url: Optional[str] = None
    full_name: Optional[str] = None
    cover_image_url: Optional[str] = None
    # NOTE: user_type intentionally omitted — privilege changes must go through admin endpoints only

class User(UserBase):
    id: int
    created_at: datetime
    user_type: Optional[str] = "private"
    cover_image_url: Optional[str] = None
    overall_rating: Optional[float] = 0.0
    response_rate: Optional[int] = 100
    average_response_time: Optional[str] = "Typically replies within 1 hour"
    trust_score: Optional[int] = 50
    followers_count: Optional[int] = 0
    following_count: Optional[int] = 0
    is_email_verified: Optional[bool] = False
    is_phone_verified: Optional[bool] = False
    is_identity_verified: Optional[bool] = False
    location: Optional[str] = ""
    is_active: Optional[bool] = True
    is_banned: Optional[bool] = False
    
    wallet_balance: Optional[float] = 0.0
    
    # KYC
    national_id: Optional[str] = None
    date_of_birth: Optional[str] = None
    id_expiry_date: Optional[str] = None
    identity_document_url: Optional[str] = None
    liveness_passed: Optional[bool] = False
    face_similarity_score: Optional[float] = None
    verification_status: Optional[str] = "pending"
    
    # Advanced Profile Ext.
    bio: Optional[str] = None
    preferred_contact: Optional[str] = None
    languages_spoken: Optional[List[str]] = None
    deals_completed: Optional[int] = 0
    cancellation_rate: Optional[int] = 0
    buyer_satisfaction: Optional[int] = 0
    
    shop_name: Optional[str] = None
    business_policy: Optional[str] = None
    shop_location: Optional[str] = None
    shop_hours: Optional[str] = None
    
    # Dynamic Ads Counts
    active_ads_count: Optional[int] = 0
    sold_ads_count: Optional[int] = 0
    total_ads_count: Optional[int] = 0

    class Config:
        from_attributes = True

class UserPrivateProfile(BaseModel):
    """
    Safe self-profile response for /me endpoint - excludes sensitive KYC fields.
    """
    id: int
    created_at: datetime
    user_type: Optional[str] = "private"
    cover_image_url: Optional[str] = None
    overall_rating: Optional[float] = 0.0
    response_rate: Optional[int] = 100
    average_response_time: Optional[str] = "Typically replies within 1 hour"
    trust_score: Optional[int] = 50
    followers_count: Optional[int] = 0
    following_count: Optional[int] = 0
    is_email_verified: Optional[bool] = False
    is_phone_verified: Optional[bool] = False
    is_identity_verified: Optional[bool] = False
    mobile_number: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    full_name: Optional[str] = None
    location: Optional[str] = ""
    is_active: Optional[bool] = True
    is_banned: Optional[bool] = False
    wallet_balance: Optional[float] = 0.0
    bio: Optional[str] = None
    preferred_contact: Optional[str] = None
    languages_spoken: Optional[List[str]] = None
    deals_completed: Optional[int] = 0
    cancellation_rate: Optional[int] = 0
    buyer_satisfaction: Optional[int] = 0
    shop_name: Optional[str] = None
    business_policy: Optional[str] = None
    shop_location: Optional[str] = None
    shop_hours: Optional[str] = None
    active_ads_count: Optional[int] = 0
    sold_ads_count: Optional[int] = 0
    total_ads_count: Optional[int] = 0
    
    class Config:
        from_attributes = True
    
    # KYC
    full_name: Optional[str] = None
    national_id: Optional[str] = None
    date_of_birth: Optional[str] = None
    id_expiry_date: Optional[str] = None
    identity_document_url: Optional[str] = None
    liveness_passed: Optional[bool] = False
    face_similarity_score: Optional[float] = None
    verification_status: Optional[str] = "pending"
    
    # Advanced Profile Ext.
    bio: Optional[str] = None
    preferred_contact: Optional[str] = None
    languages_spoken: Optional[List[str]] = None
    deals_completed: Optional[int] = 0
    cancellation_rate: Optional[int] = 0
    buyer_satisfaction: Optional[int] = 0
    
    shop_name: Optional[str] = None
    business_policy: Optional[str] = None
    shop_location: Optional[str] = None
    shop_hours: Optional[str] = None
    
    # Dynamic Ads Counts
    active_ads_count: Optional[int] = 0
    sold_ads_count: Optional[int] = 0
    total_ads_count: Optional[int] = 0

    class Config:
        from_attributes = True

class UserPublicProfile(BaseModel):
    id: int
    username: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    overall_rating: Optional[float] = 0.0
    response_rate: Optional[int] = 100
    average_response_time: Optional[str] = None
    trust_score: Optional[int] = 50
    followers_count: Optional[int] = 0
    following_count: Optional[int] = 0
    location: Optional[str] = ""
    bio: Optional[str] = None
    preferred_contact: Optional[str] = None
    languages_spoken: Optional[List[str]] = None
    deals_completed: Optional[int] = 0
    shop_name: Optional[str] = None
    active_ads_count: Optional[int] = 0
    sold_ads_count: Optional[int] = 0
    total_ads_count: Optional[int] = 0
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserReviewBase(BaseModel):
    rating: float
    text: str
    tags: List[str] = []

class UserReviewCreate(UserReviewBase):
    target_user_id: int

class UserReview(UserReviewBase):
    id: int
    reviewer_id: int
    target_user_id: int
    created_at: datetime
    
    # We can include a nested reviewer snippet if requested
    reviewer: Optional[UserPublicProfile] = None

    class Config:
        from_attributes = True

# AUTHENTICATION SCHEMAS
class RequestOTP(BaseModel):
    mobile_number: str
    method: Optional[str] = "whatsapp"

class GoogleAuthRequest(BaseModel):
    id_token: str

class FacebookAuthRequest(BaseModel):
    access_token: str

class AppleAuthRequest(BaseModel):
    id_token: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class AdminLogin(BaseModel):
    username: str
    password: str

class VerifyOTP(BaseModel):
    mobile_number: str
    otp_code: str

class OtpCodeOut(BaseModel):
    id: int
    mobile_number: str
    otp_code: str
    expires_at: datetime
    created_at: datetime
    attempts: int
    ip_address: Optional[str] = None
    
    class Config:
        from_attributes = True

class AuthResponse(BaseModel):
    token: str
    refresh_token: Optional[str] = None
    user: User

class UserMetricsBase(BaseModel):
    saved_items: int
    recently_viewed: int
    active_ads: int

class UserMetrics(UserMetricsBase):
    user_id: int
    class Config:
        from_attributes = True

class TagBase(BaseModel):
    name: str

class Tag(TagBase):
    id: int
    class Config:
        from_attributes = True

class RegionBase(BaseModel):
    name_ar: str
    name_en: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city_id: int

class RegionModel(RegionBase):
    id: int
    class Config:
        from_attributes = True

class CityBase(BaseModel):
    name_ar: str
    name_en: str

class CityModel(CityBase):
    id: int
    regions: List[RegionModel] = []
    class Config:
        from_attributes = True

class CategoryBase(BaseModel):
    parent_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    icon_name: Optional[str] = None
    color_hex: Optional[str] = None
    background_url: Optional[str] = None
    tag: Optional[str] = None
    slugs: Optional[dict] = None
    order_index: Optional[int] = 0

class Category(CategoryBase):
    id: int
    linked_tags: Optional[List[Tag]] = []
    ads_count: Optional[int] = 0
    class Config:
        from_attributes = True

class CategoryCreate(CategoryBase):
    linked_tags: Optional[List[str]] = []

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    description: Optional[str] = None
    icon_name: Optional[str] = None
    color_hex: Optional[str] = None
    background_url: Optional[str] = None
    tag: Optional[str] = None
    slugs: Optional[dict] = None
    order_index: Optional[int] = None
    linked_tags: Optional[List[str]] = [] # We accept string list of tag names on update

class CategoryReorder(BaseModel):
    id: int
    order_index: int

class AdBase(BaseModel):
    title: str
    description: str
    price: float
    location: str
    image_url: Optional[str] = None
    category_id: Optional[int] = None
    attributes: Optional[dict] = None
    video_url: Optional[str] = None
    is_featured: Optional[bool] = False

class AdCreate(AdBase):
    linked_tags: Optional[List[str]] = []
    image_urls: Optional[List[str]] = []
    phone_number: Optional[str] = None
    real_estate_detail: Optional[dict] = None

class AdUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    location: Optional[str] = None
    image_url: Optional[str] = None
    category_id: Optional[int] = None
    attributes: Optional[dict] = None
    video_url: Optional[str] = None
    linked_tags: Optional[List[str]] = []
    image_urls: Optional[List[str]] = []
    phone_number: Optional[str] = None
    real_estate_detail: Optional[dict] = None
    is_published: Optional[bool] = None
    is_featured: Optional[bool] = None

class AdDraftCreate(BaseModel):
    category_id: Optional[int] = None
    title: Optional[str] = ""
    description: Optional[str] = ""
    price: Optional[float] = 0.0
    location: Optional[str] = ""
    image_url: Optional[str] = None
    attributes: Optional[dict] = None
    linked_tags: Optional[List[str]] = []
    image_urls: Optional[List[str]] = []
    phone_number: Optional[str] = None
    real_estate_detail: Optional[dict] = None

class AdDraftUpdate(AdDraftCreate):
    is_published: Optional[bool] = None

class AdRealEstateDetailBase(BaseModel):
    bathrooms: Optional[Any] = None
    furnished: Optional[str] = None
    build_area: Optional[Any] = None
    floor: Optional[str] = None
    building_age: Optional[str] = None
    rent_duration: Optional[str] = None
    view_orientation: Optional[str] = None
    key_features: Optional[List[str]] = None
    additional_features: Optional[List[str]] = None
    nearby_locations: Optional[List[str]] = None

class AdRealEstateDetail(AdRealEstateDetailBase):
    id: int
    ad_id: int
    
    class Config:
        from_attributes = True

class Ad(AdBase):
    id: int
    user_id: int
    views: int = 0
    is_hot: bool = False
    is_published: bool = False
    is_featured: bool = False
    duplicate_status: Optional[str] = None
    highest_duplicate_score: Optional[int] = None
    linked_tags: Optional[List[Tag]] = []
    
    @field_validator('location', mode='before')
    @classmethod
    def format_location(cls, v: Any) -> Any:
        # The DB stores "City, Region" (e.g. "إربد, حكما").
        # We just send it as is, so the frontend displays City (right) then Region (left).
        return v
        
    owner: Optional[UserPublicProfile] = None
    
    source_type: str = "ORGANIC_USER"
    source_url: Optional[str] = None
    raw_description: Optional[str] = None
    phone_number: Optional[str] = None
    rooms: Optional[Any] = None
    image_urls: Optional[List[str]] = []
    
    real_estate_detail: Optional[AdRealEstateDetail] = None
    message: Optional[str] = None

    created_at: datetime
    updated_at: datetime
    
    expires_at: Optional[datetime] = None
    is_paused: bool = False
    is_sold: bool = False
    is_rejected: bool = False
    rejected_reason: Optional[str] = None
    is_boosted: bool = False
    boost_expiry: Optional[datetime] = None
    chats_count: int = 0
    favorites_count: int = 0
    is_saved: Optional[bool] = False
    last_republished_at: Optional[datetime] = None
    cpc_bid: Optional[float] = 0.0

    class Config:
        from_attributes = True

class MyAdResponse(Ad):
    status: str = "Active"
    performance_score: int = 0
    suggested_action: Optional[str] = None
    
    class Config:
        from_attributes = True

class MyAdsDashboardSummary(BaseModel):
    totalAds: int
    activeAds: int
    expiredAds: int
    pendingAds: int
    soldAds: int
    pausedAds: int
    boostedAds: int
    totalViews: int
    totalChats: int
    totalFavorites: int

class BulkActionRequest(BaseModel):
    ad_ids: List[int]
    action: str

class LiveTickerBase(BaseModel):
    message: str

class LiveTicker(LiveTickerBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True

class StoryBase(BaseModel):
    image_url: str
    title: Optional[str] = None

class Story(StoryBase):
    id: int
    user_id: int
    created_at: datetime
    owner: Optional[UserPublicProfile] = None
    
    class Config:
        from_attributes = True
from typing import Optional, List

class ScrapeRequest(BaseModel):
    category_id: Optional[int] = None
    source_url: str
    default_city: str = "عمان"
    limit: int = 1

class SavedGroupBase(BaseModel):
    name: str
    url: str
    category_id: Optional[int] = None
    is_active: bool = True

class SavedGroupCreate(SavedGroupBase):
    pass

class SavedGroup(SavedGroupBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# NOTIFICATION SCHEMAS
class NotificationOut(BaseModel):
    id: int
    target_user_id: int
    title: str
    body: Optional[str] = None
    type: Optional[str] = None
    reference_id: Optional[int] = None
    is_read: bool = False
    created_at: datetime

    class Config:
        from_attributes = True

class DeviceTokenCreate(BaseModel):
    fcm_token: str
    device_type: Optional[str] = None

class AdminNotificationCreate(BaseModel):
    target_user_id: str  # Can be a specific ID like "5" or the string "all"
    title: str
    body: str
    type: Optional[str] = "admin_alert"

class ChatAlertCreate(BaseModel):
    target_user_id: int
    sender_name: str
    message_preview: str
    ad_id: str
    ad_title: Optional[str] = ""
    chat_id: Optional[str] = ""
    message_id: Optional[str] = ""

# TRACKING SCHEMAS
class LogEventRequest(BaseModel):
    action_type: str
    category_id: Optional[int] = None
    filters_json: Optional[dict] = None

class UserActivityLogOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    action_type: str
    category_id: Optional[int] = None
    filters_json: Optional[dict] = None
    created_at: datetime
    class Config:
        from_attributes = True

class DashboardInsightsOut(BaseModel):
    total_logs: int
    top_categories: list
    recent_activity: list
    filter_analytics: list
    location_stats: list
    real_estate_stats: list

class PersonalizedAdsOut(BaseModel):
    title: str
    category_id: Optional[int] = None
    ads: List[Ad]
    filters_json: Optional[dict] = None
    
    class Config:
        from_attributes = True

# AD REPORT SCHEMAS
class AdReportCreate(BaseModel):
    reason: str
    comments: Optional[str] = None

class AdReportOut(BaseModel):
    id: int
    ad_id: int
    user_id: Optional[int] = None
    reason: str
    comments: Optional[str] = None
    status: str
    created_at: datetime
    
    # We can include ad title and username for dashboard convenience
    ad_title: Optional[str] = None
    reporter_name: Optional[str] = None
    reporter_phone: Optional[str] = None

    class Config:
        from_attributes = True

class CategoryFiltersPrefs(BaseModel):
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    tags: Optional[List[str]] = []
# --- Saved Filter Schemas ---

class SavedFilterBase(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = None
    search_query: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    tags: Optional[List[str]] = []
    locations: Optional[List[str]] = []
    alert_frequency: Optional[str] = "none"
    is_active: Optional[bool] = True

class SavedFilterCreate(SavedFilterBase):
    pass

class SavedFilterResponse(SavedFilterBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class SupportMessageBase(BaseModel):
    message: str
    sender: str

class SupportMessageCreate(BaseModel):
    message: str

class SupportMessage(SupportMessageBase):
    id: int
    user_id: int
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class BlockedPhoneNumberBase(BaseModel):
    phone_number: str

class BlockedPhoneNumberCreate(BlockedPhoneNumberBase):
    pass

class BlockedPhoneNumberResponse(BlockedPhoneNumberBase):
    created_at: datetime
    class Config:
        from_attributes = True

