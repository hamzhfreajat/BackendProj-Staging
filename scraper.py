import re
import asyncio
import time
from sqlalchemy.orm import Session
from datetime import datetime
import models
from mapper import get_dynamic_location_rules, map_location, get_location_map, map_location_with_fallback

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import google.generativeai as genai
import os
import random
import asyncio
import time
from dotenv import load_dotenv
import aiohttp
from playwright.async_api import async_playwright

load_dotenv()

# Global tracking object for the active scrape session
active_scrape_status = {
    "is_scraping": False,
    "progress": 0,
    "total": 0,
}

city_regions_map = get_location_map()

# --- Pydantic Schema for Gemini Strict JSON Extraction ---
class ExtractedAdAttributes(BaseModel):
    rooms: Optional[int] = Field(description="Number of rooms, if mentioned")
    bathrooms: Optional[int] = Field(description="Number of bathrooms")
    furnished: Optional[str] = Field(description="Furnished state. Match exactly: مفروشة, غير مفروشة, مفروش جزئياً")
    floor: Optional[str] = Field(description="Floor level. Match exactly: طابق التسوية, طابق شبه أرضي, الطابق الأرضي, 1, 2, 3, 4, 5, 6, 7, طابق أخير, روف, طابق أخير مع روف")
    key_features: List[str] = Field(description="Array of features. Match exactly if possible: تكييف مركزي, تدفئة, شرفة / بلكونة, غرفة خادمة, غرفة غسيل, خزائن حائط, مسبح خاص, سخان شمسي, زجاج شبابيك مزدوج, مطبخ راكب, صالون واسع, تأسيس تكييف, مناسبة لعرسان, كراج, سوبر ديلوكس")
    has_terrace: Optional[str] = Field(description="Match exactly: نعم, لا if the ad mentions having a terrace (ترس)")
    terrace_area: Optional[str] = Field(description="Terrace area in square meters if mentioned")
    
    # 1. Basic Info (Shared Rooms)
    room_type: Optional[str] = Field(description="Type of room. Match with: غرفة خاصة, غرفة مشتركة, سرير في غرفة, استوديو ملحق بالسكن")
    target_audience: List[str] = Field(description="Who is this for? e.g. شباب, طلاب, بنات, عائلات صغيرة, وافدين")
    room_capacity: Optional[str] = Field(description="Room capacity if mentioned: شخص واحد, شخصين, 3 أشخاص, الخ")
    current_occupants: Optional[int] = Field(description="Total number of people currently in the apartment (e.g. 1, 2, 3...)")
    rent_duration: Optional[str] = Field(description="Duration. Match exactly: يومي, أسبوعي, شهري, كل 3 أشهر, كل أربع أشهر, كل 5 أشهر, كل 6 أشهر, سنوي")
    
    # 2. Cost & Bills
    rent_includes: List[str] = Field(description="What's included in rent: الكهرباء, الماء, الإنترنت, التدفئة, الغاز, حارس العمارة, غير شامل")
    payment_frequency: Optional[str] = Field(description="e.g. دفع شهري, دفع كل 3 شهور, دفع فصلي")
    insurance_required: Optional[bool] = Field(description="True if insurance/deposit is required, False if without insurance")
    payment_method: Optional[str] = Field(description="Match exactly: كاش, أقساط, كاش أو أقساط")
    
    # 3. Room Specs
    bathroom_type: Optional[str] = Field(description="Bathroom type: حمام ماستر, حمام مشترك مع شخص واحد, حمام مشترك مع باقي الشقة")
    room_contents: List[str] = Field(description="Items in room: سرير مفرد, سرير مزدوج, خزانة ملابس, مكتب دراسة, شاشة تلفزيون, ثلاجة صغيرة")
    room_features: List[str] = Field(description="Room perks: مكيف مستقل, رديتر تدفئة, مروحة سقف, بلكونة, شباك كبير")
    
    # 4. Shared Space Specs (Apartment)
    shared_spaces: List[str] = Field(description="Shared areas: صالة جلوس واسعة, طاولة طعام, تراس, حمام ضيوف")
    kitchen_appliances: List[str] = Field(description="Kitchen: مطبخ راكب, ثلاجة كبيرة, فريزر منفصل, غاز, مايكرويف, كولر ماء, جلاية")
    laundry_appliances: List[str] = Field(description="Laundry: غسالة أوتوماتيك, نشافة ملابس, مكواة, منشر غسيل")
    
    # 5. House Rules
    smoking_rules: Optional[str] = Field(description="Smoking: التدخين مسموح, التدخين مسموح في البلكونة فقط, مسموح بالتدخين الإلكتروني فقط, يمنع التدخين نهائياً")
    quietness_rules: Optional[str] = Field(description="Quietness: سكن هادئ جداً, سكن مرن")
    guests_rules: Optional[str] = Field(description="Guests: مسموح بالزوار, يمنع الزوار")
    pets_rules: Optional[str] = Field(description="Pets: مسموح, يمنع اصطحاب الحيوانات")
    cleaning_rules: Optional[str] = Field(description="Cleaning: جدول تنظيف مشترك, وجود عاملة نظافة")
    
    # 6. Building Specs
    building_age: Optional[str] = Field(description="Age of building: Match exactly: 0 - 11 شهر, 1 - 5 سنوات, 6 - 9 سنوات, 10 - 19 سنوات, +20 سنة")
    building_features: List[str] = Field(description="Building perks. Match exactly if possible: يوجد مصعد, حديقة, حارس / أمن وحماية, كراج تفك, منطقة شواء, نظام كهرباء احتياطي للطوارئ, بركة سباحة, انتركم")
    
    # Lands & Commercial Specs
    land_type: Optional[str] = Field(description="Match exactly: سكنية, تجارية, زراعية, صناعية, استثمارية, سياحية, مختلطة, أخرى")
    zoning_classification: Optional[str] = Field(description="Match exactly: سكن أ, سكن ب, سكن ج, سكن د, تجاري, زراعي, صناعي, أخرى")
    facade: Optional[str] = Field(description="Match exactly: شقة طابقية, شمالية, جنوبية, شرقية, غربية, شمالية شرقية, شمالية غربية, جنوبية شرقية, جنوبية غربية")
    geometric_shape: Optional[str] = Field(description="Match exactly: مستطيل, مربع, غير منتظم, زاوية / شارعَين")
    topography: Optional[str] = Field(description="Match exactly: مستوية, منحدرة, جبلية, واد")
    available_services: List[str] = Field(description="Match exactly: ماء, كهرباء, صرف صحي, إنترنت, شوارع معبدة")
    ownership_type: Optional[str] = Field(description="Match exactly: ملك, تفويض, أخرى")
    is_mortgaged: Optional[str] = Field(description="Match exactly: نعم, لا")
    installment_possible: Optional[str] = Field(description="Match exactly: نعم, لا")
    
    # 7. Locations
    nearby_places: List[str] = Field(description="Nearby: محطة الباص السريع, جامعة, سوبر ماركت, صيدلية, مطاعم")
    
    payment_method: List[str] = Field(description="How payment works? e.g. من المالك, مكتب عقاري, تقسيط")
    phone_number: Optional[str] = Field(description="Any extracted Jordanian phone number")

class ExtractedAd(BaseModel):
    post_index: int = Field(description="The index of the post in the prompt array (0 to 9)")
    category_id: int = Field(description="The ID of the category that best matches this post (e.g., 301 for apartments, 101 for cars, etc.)")
    title: str = Field(description="A clean, concise title for the ad (max 80 chars)")
    description: str = Field(description="The full ad text cleaned up")
    price: float = Field(description="The extracted price in JOD. Return 0 if not found")
    location: Optional[str] = Field(description="The geographic location. For real estate format as 'المدينة, المنطقة'. CRITICAL: Any mention of Aqaba residential zones like 'التاسعة', 'المنطقة السكنية الثامنة', 'المنطقة الخامسة' MUST be standardized to 'العقبة, السكنية 9', 'العقبة, السكنية 8', 'العقبة, السكنية 5', etc. Do not hallucinate cities if not mentioned.")
    attributes: ExtractedAdAttributes = Field(description="Detailed property / vehicle attributes")

def run_scraper_task(request_data: dict, db: Session):
    """
    Synchronous wrapper to ensure Playwright runs in a clean Proactor Event Loop on Windows,
    bypassing Uvicorn's SelectorEventLoop restrictions.
    """
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    try:
        asyncio.run(_async_run_scraper_task(request_data, db))
    except Exception as e:
        print(f"ERROR: [Scraper Wrapper] {e}")
        active_scrape_status["is_scraping"] = False
        active_scrape_status["message"] = "فشل في بدء عملية الاستخراج"

def extract_all_images(data):
    """Recursively search for image URLs in the post data."""
    found_images = []
    
    # Signatures typical of Facebook UI icons or user profile thumbnails
    ignore_patterns = [
        'dst-jpg_s', 'dst-jpg_p', '100x100', '80x80', '72x72', '50x50', '32x32', 
        '/cp0/', 'emoji', 'icon'
    ]
    
    def is_valid_ad_image(url):
        if not url or not isinstance(url, str):
            return False
        if not url.startswith('http'):
            return False
        
        url_lower = url.lower()
        if any(pattern in url_lower for pattern in ignore_patterns):
            return False
            
        return True

    def search_dict(d):
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, str) and ('.jpg' in v or '.png' in v or '.webp' in v):
                    clean_v = v.split(' ')[0] # Handle srcset spaces
                    if is_valid_ad_image(clean_v) and clean_v not in found_images:
                        found_images.append(clean_v)
                elif isinstance(v, (dict, list)):
                    search_dict(v)
        elif isinstance(d, list):
            for item in d:
                search_dict(item)
                
    if isinstance(data, dict):
        if is_valid_ad_image(data.get('image')) and data.get('image') not in found_images:
            found_images.append(data.get('image'))
        if is_valid_ad_image(data.get('video_thumbnail')) and data.get('video_thumbnail') not in found_images:
            found_images.append(data.get('video_thumbnail'))
            
        # Explicit check for album_preview array that appears in some groups
        if isinstance(data.get('album_preview'), list):
            for album_item in data['album_preview']:
                if isinstance(album_item, dict):
                    img_uri = album_item.get('image_file_uri') or album_item.get('url')
                    if is_valid_ad_image(img_uri) and img_uri not in found_images:
                        found_images.append(img_uri)
            
    search_dict(data)
    found_images = [img for img in found_images if img]
    return found_images[:6]

async def _async_run_scraper_task(request_data: dict, db: Session):
    """
    Background worker function that fetches real data from the provided URL.
    It uses Playwright to render JavaScript and then parses standardized listing patterns.
    """
    url = request_data.get("source_url")
    category_id = request_data.get("category_id")
    city = request_data.get("default_city", "عمان")
    limit = request_data.get("limit", 5)
    
    # Extract Group ID
    import re
    group_id = url
    fb_group_match = re.search(r'facebook\.com/groups/([^/?\s]+)', str(url))
    if fb_group_match:
        group_id = fb_group_match.group(1)
    elif "g=" in url:
        g_match = re.search(r'g=([^&\s]+)', url)
        if g_match:
            group_id = g_match.group(1)
            
    # Initialize Status
    active_scrape_status["is_scraping"] = True
    active_scrape_status["progress"] = 0
    active_scrape_status["total"] = limit
    active_scrape_status["message"] = f"Initiating Scrape for {url}"
    
    try:
        print(f"INFO: [Scraper] Initiating Scrape for group '{group_id}' with limit {limit}")
    except Exception:
        pass
    
    # --- PLAYWRIGHT DESKTOP SCRAPING ROUTE ---
    try:
        raw_posts = []
        seen_texts = set()

        from playwright.async_api import async_playwright
        import os
        import subprocess

        # Enforce Mobile site for easier DOM extraction (bypasses React virtual recycling)
        mobile_url = url.replace('www.facebook.com', 'm.facebook.com')
        
        active_scrape_status["message"] = f"جاري سحب البيانات من {mobile_url}..."
        print(f"INFO: [Scraper] Navigating to URL: {mobile_url} via Headless Playwright")
        
        async with async_playwright() as p:
            try:
                print("INFO: [Scraper] Attempting to connect to real Chrome via CDP...")
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            except Exception:
                print("WARNING: [Scraper] Local CDP not found. Attempting to spawn Chrome automatically...")
                
                # Setup a persistent user data directory for Facebook login
                user_data_dir = os.path.join(os.getcwd(), 'chrome_profile')
                os.makedirs(user_data_dir, exist_ok=True)
                
                chrome_paths = [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                ]
                
                chrome_exe = next((p for p in chrome_paths if os.path.exists(p)), None)
                if not chrome_exe:
                    active_scrape_status["is_scraping"] = False
                    active_scrape_status["message"] = "لم يتم العثور على متصفح Chrome."
                    return
                
                subprocess.Popen([
                    chrome_exe,
                    "--remote-debugging-port=9222",
                    f"--user-data-dir={user_data_dir}",
                    "--no-first-run",
                    "--no-default-browser-check"
                ])
                await asyncio.sleep(4)  # Wait for Chrome to boot
                
                try:
                    browser = await p.chromium.connect_over_cdp("http://localhost:9222")
                except Exception as final_e:
                    print(f"ERROR: [Scraper] CDP Connection failed even after spawn: {final_e}")
                    active_scrape_status["is_scraping"] = False
                    active_scrape_status["message"] = "فشل تشغيل متصفح Chrome. يرجى إغلاق كل نوافذ كروم والمحاولة مجدداً."
                    return
            
            try:
                # Use the user's primary browsing context so we get their Facebook cookies
                context = browser.contexts[0]
                page = await context.new_page()
                print("INFO: [Scraper] Connected successfully to real Chrome.")
            except Exception as e:
                print(f"ERROR: [Scraper] Failed to create new page: {e}")
                active_scrape_status["is_scraping"] = False
                active_scrape_status["message"] = "حدث خطأ أثناء فتح نافذة جديدة في المتصفح."
                return
            
            print("INFO: [Scraper] Loading Mobile page...")
            await page.set_viewport_size({"width": 375, "height": 812}) # Mobile viewport
            await page.goto(mobile_url, wait_until="domcontentloaded", timeout=60000)
            
            print('INFO: [Scraper] Scrolling to load batch on mobile...')
            previous_height = 0
            for i in range(8):
                 try:
                     await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                     await asyncio.sleep(3) # Wait for network requests on mobile
                     
                     new_height = await page.evaluate("document.body.scrollHeight")
                     if new_height == previous_height:
                         break
                     previous_height = new_height
                 except Exception as e:
                     print(f"WARNING: Scroll interrupted: {e}")
                     break
                 
            print('INFO: [Scraper] Extracting visible posts from Mobile structural DOM...')
            # Mobile Facebook has a simpler structure and doesn't destroy old DOM nodes eagerly
            try:
                # Give the page a moment to finish any lingering client rendering
                await asyncio.sleep(2)
                
                # Expand "See more" texts
                print('INFO: [Scraper] Expanding text nodes by clicking read more buttons...')
                await page.evaluate("""
                    () => {
                        const words = ["عرض المزيد", "قراءة المزيد", "See more", "Read more", "مزيد", "more"];
                        const elements = document.querySelectorAll('[data-sigil="more"], a, span, div[role="button"]');
                        for (let el of elements) {
                            if (el.innerText) {
                                let text = el.innerText.trim();
                                let match = words.some(w => text.includes(w)) && text.length < 25;
                                if (match || el.getAttribute('data-sigil') === 'more') {
                                    try { el.click(); } catch (e) {}
                                }
                            }
                        }
                    }
                """)
                await asyncio.sleep(2) # wait for DOM to expand
                
                # Debug dump
                with open('debug_dom.html', 'w', encoding='utf-8') as f:
                    f.write(await page.content())
                
                # Mobile posts typically have data-sigil="story-div" or are standard `article` tags
                articles = await page.locator('div[data-sigil="story-div"], article').all()
                for article in articles:
                    try:
                        text = await article.inner_text()
                        if text and len(text) > 40 and 'Like' not in text and 'Comment' not in text and 'أعجبني' not in text and 'تعليق' not in text:
                            
                            import re
                            text = re.split(r'\\bLike\\b|\\bComment\\b|\\bShare\\b|\\bأعجبني\\b|\\bتعليق\\b|\\bمشاركة\\b', text)[0].strip()
                            fingerprint = "".join(text.split())[:100]
                            
                            if fingerprint not in seen_texts:
                                seen_texts.add(fingerprint)
                                
                                # Find mobile specific images
                                imgs = await article.locator('i[role="img"], img').all()
                                images = []
                                for img in imgs:
                                    src = await img.get_attribute('src')
                                    # Handle mobile background-image styles holding image URLs
                                    if not src:
                                        style = await img.get_attribute('style')
                                        if style and 'background-image' in style and 'url(' in style:
                                            match = re.search(r'url\\(["\']?(.*?)["\']?\\)', style)
                                            if match:
                                                src = match.group(1)
                                                
                                    if src and ('scontent' in src or 'external' in src or 'fbcdn' in src) and 'emoji' not in src:
                                        images.append(src)
                                        
                                raw_posts.append({
                                    "text": text,
                                    "images": list(set(images))[:5],
                                    "post_url": mobile_url
                                })
                    except Exception as e:
                        print(f"Parse error: {e}")
                        continue
                        
            except Exception as e:
                print(f"Selector error: {e}")
                pass
                        
            print(f"INFO: [Scraper] Collected {len(raw_posts)} total posts from Mobile UI...")
            
            # Filter out posts without images BEFORE sending to AI
            raw_posts = [p for p in raw_posts if len(p.get('images', [])) > 0]
            print(f"INFO: [Scraper] Kept {len(raw_posts)} posts that have images.")
            
            await page.close()

        if not raw_posts:
            print("WARNING: [Scraper] No usable posts with images extracted by Playwright.")
            active_scrape_status["is_scraping"] = False
            active_scrape_status["message"] = "لم يتم العثور على أي إعلانات في الرابط."
            return
            
        # Optional: Save raw posts locally to debug
        try:
            with open("debug_fb_posts.txt", "w", encoding="utf-8") as f:
                for idx, rp in enumerate(raw_posts):
                    f.write(f"--- POST {idx} ---\\n")
                    f.write(f"TEXT:\\n{rp['text']}\\n")
                    f.write(f"IMAGES: {rp['images']}\\n")
                    f.write(f"URL: {rp.get('post_url', '')}\\n\\n")
        except Exception:
            pass

        # GEMINI AI BATCH PARSING
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            print("ERROR: [Scraper] GEMINI_API_KEY is not set.")
            active_scrape_status["is_scraping"] = False
            active_scrape_status["message"] = "مفتاح Gemini API مفقود! يرجى إضافته في الإعدادات."
            return
            
        genai.configure(api_key=gemini_api_key)
        db_categories = db.query(models.Category).all()
        parent_ids = {c.parent_id for c in db_categories if c.parent_id is not None}
        
        categories_context_lines = []
        for cat in db_categories:
            if cat.id in parent_ids:
                continue # Skip parent categories
                
            parent_name = ""
            if cat.parent_id:
                parent = next((p for p in db_categories if p.id == cat.parent_id), None)
                if parent:
                    parent_name = f"{parent.name} > "
            
            categories_context_lines.append(f"ID: {cat.id} | Name: {parent_name}{cat.name} | Tags: {cat.slugs}")
            
        categories_context = "\n".join(categories_context_lines)

        dynamic_rules_text = get_dynamic_location_rules()
        dynamic_rules_instruction = f"\\n10. DYNAMIC LOCATION OVERRIDES:\\n{dynamic_rules_text}" if dynamic_rules_text else ""

        system_instruction = (
            "You are an expert AI data extraction assistant specialized in Jordanian classifieds ( العقارات, السيارات, الوظائف ).\\n"
            "You will receive an array of raw text posts from Facebook groups or classifieds sites.\\n"
            "1. Read EACH post individually.\\n"
            "2. If it is a generic post without a clear ad ('Good morning', 'Please like my page'), SKIP it. Do NOT return it in the JSON array.\\n"
            "3. For valid ads, extract the fields exactly as required by the schema.\\n"
            f"4. If you can confidently determine the Category ID from this list, use it:\\n{categories_context}\\n"
            "If you CANNOT determine the ID, you may leave `category_id` as 0.\\n"
            "5. Ensure prices are purely numeric (JOD). IMPORTANT: Daily/monthly apartment rentals can legitimately have a price between 1-99 JOD. However, if the ad is for an ANNUAL rent (سنوي) or SALE (للبيع) and the price mentioned is between 1-99 JOD (e.g. '12 JOD'), DO NOT extract it! Return 0. DO NOT confuse random numbers ('used 1 month', '99% clean') with a price. If no real monetary price is mentioned, return 0.\\n"
            "6. CRITICAL LOCATION RULES: Be very precise with locations. 'العاشرة' typically means 'العقبة, المنطقة العاشرة' NOT 'عمان, الدوار العاشر'. Do not confuse 'بدر' with 'بدر الجديدة'.\n7. NEVER output relative descriptions like 'قرب', 'خلف', 'بجانب', 'شرق', 'جنوب', 'مقابل'. You MUST extract ONLY the exact official name of the neighborhood/region.\n8. 'البارحة', 'مستشفى بديعة', 'دوار صحارى', 'دوار العيادات', 'دوار الثقافة', 'دوار النسيم', 'مجمع عمان', 'شارع فلسطين', 'بن العميد', 'خلف بن العميد' are ALL strictly in 'إربد' (Irbid), NOT Amman! If you see them, format as 'إربد, بن العميد' etc. Do not hallucinate cities. You MUST ONLY use regions that officially exist. If the neighborhood mentioned is completely unknown, not a standard region, or you are completely unsure, you MUST output the City name followed by \'أخرى\' (e.g. \'عمان, أخرى\'). NEVER invent or hallucinate a new region name.\n9. CRITICAL: If the location mentions 'عزريت' or 'قصر العوادين' (or variants like 'لواء بني كنانة, عزريت' or 'قرب قصر العوادين'), ALWAYS format the location EXACTLY as 'قصر العوادين , عزريت' without any additional words."
            f"{dynamic_rules_instruction}"
        )
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_instruction)
        
        processed_count = 0
        
        for i in range(0, len(raw_posts), 5): # Chunks of 5
            batch = raw_posts[i:i+5]
            prompts_array = []
            
            for idx, post in enumerate(batch):
                prompts_array.append(f"POST {idx}:\\n{post['text']}")
                
            prompt_text = "Extract the following posts into the JSON Schema array:\\n" + "\\n---\\n".join(prompts_array)
            
            try:
                print(f"INFO: [Scraper] Sending batch of {len(batch)} to Gemini...")
                active_scrape_status["message"] = f"جاري تحليل المنشورات بالذكاء الاصطناعي ({processed_count}/{len(raw_posts)})..."
                
                result = model.generate_content(
                    prompt_text,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        response_schema=list[ExtractedAd],
                    ),
                )
                
                import json
                raw_json = result.text.strip()
                if raw_json.startswith("```json"):
                    raw_json = raw_json[7:]
                    if raw_json.endswith("```"):
                        raw_json = raw_json[:-3]
                elif raw_json.startswith("```"):
                    raw_json = raw_json[3:]
                    if raw_json.endswith("```"):
                        raw_json = raw_json[:-3]
                        
                extracted_ads = json.loads(raw_json.strip())
                
                for ai_ad in extracted_ads:
                    post_index = ai_ad.get("post_index")
                    if post_index is not None and post_index < len(batch):
                        original_post = batch[post_index]
                        
                        # Merge images
                        attributes_payload = ai_ad.get("attributes", {})
                        if original_post['images']:
                            attributes_payload['image_urls'] = original_post['images'][:6]
                            
                        # Fallback logic for Category ID
                        final_category_id = ai_ad.get("category_id")
                        valid_category_ids = {c.id for c in db_categories}
                        
                        if not final_category_id or final_category_id not in valid_category_ids:
                            final_category_id = category_id
                            
                        # If we still don't have a valid category ID, we can't save it to the DB! skip.
                        if not final_category_id or final_category_id not in valid_category_ids:
                            print(f"INFO: [Scraper] Skipping post due to invalid or missing category ID ({final_category_id}).")
                            continue
                            
                        # Prevents duplicates by checking if the exact raw text is already in the database
                        existing_ad = db.query(models.Ad).filter(models.Ad.raw_description == original_post['text']).first()
                        if existing_ad:
                            print(f"INFO: [Scraper] Skipping duplicate post (already exists in DB).")
                            continue
                            
                        try:
                            # 1. Create User
                            user = db.query(models.User).filter(models.User.email == "ai_scraper@system.com").first()
                            if not user:
                                user = models.User(
                                    email="ai_scraper@system.com",
                                    username="أحمد صالح",
                                    full_name="أحمد صالح",
                                    hashed_password="mock",
                                    followers_count=random.randint(5000, 9500)
                                )
                                db.add(user)
                                db.commit()
                                db.refresh(user)

                            # 2. Add Location fallback
                            loc = ai_ad.get("location")
                            raw_text = original_post.get('text', '')
                            if loc:
                                mapped_loc = map_location_with_fallback(loc, raw_text, city_regions_map, city)
                                if mapped_loc:
                                    loc = mapped_loc
                            if not loc:
                                loc = city

                            # 3. Create Ad
                            new_ad = models.Ad(
                                title=ai_ad.get("title", "")[:255],
                                description=ai_ad.get("description", ""),
                                raw_description=original_post['text'], # Save raw text for future duplicate checking
                                price=ai_ad.get("price") or 0.0,
                                location=loc[:255],
                                source_url=original_post.get("post_url", url)[:255],
                                source_type=models.SourceType.SCRAPER_BOT,
                                is_published=True,
                                category_id=final_category_id,
                                user_id=user.id,
                                image_url=attributes_payload.get('image_urls', [])[0] if attributes_payload.get('image_urls') else None,
                                attributes=attributes_payload
                            )
                            db.add(new_ad)
                            db.commit()
                            db.refresh(new_ad)
                            
                            try:
                                from search_service import SearchService
                                SearchService.sync_ad_to_search_index(db, new_ad)
                            except Exception as sync_e:
                                print(f"WARNING: Failed to sync ad {new_ad.id} to search index: {sync_e}")

                            processed_count += 1
                            
                            # Update Progress
                            active_scrape_status["progress"] = processed_count
                            
                            # Break the inner extraction loop if we've reached the user's requested limit
                            if processed_count >= limit:
                                break

                        except Exception as inner_e:
                            print(f"WARNING: [Scraper] Error saving individual AI ad to DB: {inner_e}")
                            db.rollback()
                            
            except Exception as e:
                print(f"ERROR: [Scraper] Gemini Call failed: {e}")
                await asyncio.sleep(5) # rate limit backoff
                
            # Break the outer batch loop early if the user's limit is satisfied
            if processed_count >= limit:
                break
                
        active_scrape_status["is_scraping"] = False
        active_scrape_status["message"] = f"تم الانتهاء بنجاح. تم استخراج {processed_count} باستخدام الذكاء الاصطناعي."
        print(f"INFO: [Scraper] Finished processing {processed_count} items via Gemini.")

    except Exception as e:
        print(f"CRITICAL ERROR: [Scraper] Main scraping task failed: {e}")
        active_scrape_status["is_scraping"] = False
        active_scrape_status["message"] = f"حدث خطأ غير متوقع: {str(e)}"
        
    finally:
        db.close()
    
async def run_periodic_scraper():
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _sync_run_periodic_loop)

def _sync_run_periodic_loop():
    import sys
    import asyncio
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    # Create a fresh isolated loop for this thread to guarantee Playwright works
    new_loop = asyncio.ProactorEventLoop() if sys.platform == 'win32' else asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(_async_run_periodic_scraper())

async def _async_run_periodic_scraper():
    """ Runs every 60 seconds. Queries active SavedGroups and runs the scraper against them. """
    from database import SessionLocal
    import models
    while True:
        try:
            print("INFO: [Periodic] Checking for active saved groups to scrape...")
            db = SessionLocal()
            active_groups = db.query(models.SavedGroup).filter(models.SavedGroup.is_active == True).all()
            
            for group in active_groups:
                print(f"INFO: [Periodic] Triggering auto-scape for group {group.name} | {group.url}")
                req_data = {
                    "source_url": group.url,
                    "category_id": group.category_id,
                    "default_city": "عمان",
                    "limit": 5
                }
                
                # Prevent parallel overlapping tasks on the same DB session
                await _async_run_scraper_task(req_data, db)
                
            db.close()
        except Exception as e:
            print(f"ERROR: [Periodic] {e}")
            
        await asyncio.sleep(60)

# Quick Print Tests for Regex Verification if ran directly
if __name__ == "__main__":
    tests = [
        "079-123 4567",
        "٠٧٨١١١٢٢٣٣",
        "الف دينار",
        "15 ألف دينار",
        "400jd",
        "شقة 3 غرف نوم"
    ]
    
    print("--- REGEX TESTS ---")
    for t in tests:
        print(f"Text: '{t}'")
        print(f"  Phone: {extract_jo_phone(t)}")
        print(f"  Price: {extract_price(t)}")
        print(f"  Rooms: {extract_rooms(t)}")
        print("-" * 20)
