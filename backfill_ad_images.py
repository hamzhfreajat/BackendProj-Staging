"""
One-off: convert the images of existing ads to the optimized format
(see image_processing.py) so old ads load as fast as new ones.

For every ad image that is not yet under "img/", it downloads the original,
stores the full + card sizes, and points the ad at the new URL. Original files
are left in the bucket, so the change can be undone from the printed log.

    python backfill_ad_images.py                 # dry run: shows what would change
    python backfill_ad_images.py --apply         # do it
    python backfill_ad_images.py --apply --limit 200
    python backfill_ad_images.py --apply --ad-id 61766
    python backfill_ad_images.py --apply --source organic   # only ads posted by users

Safe to stop and re-run: converted images are skipped.
"""
import argparse
import concurrent.futures
import json
import sys

import requests
from sqlalchemy import text

from database import SessionLocal
from image_processing import IMAGE_PREFIX, store_image
from media_router import get_r2_client

MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024


def is_converted(url: str) -> bool:
    return f"/{IMAGE_PREFIX}" in url


def parse_image_url_column(value):
    """ads.image_url holds either one URL or a JSON list of URLs. Returns (urls, is_json_list)."""
    if not value:
        return [], False
    value = value.strip()
    if value.startswith("["):
        try:
            return [str(u) for u in json.loads(value)], True
        except ValueError:
            pass
    return [value], False


def convert(url: str, r2_client, cache: dict) -> str:
    """Returns the new URL, or the original one when it can't be converted."""
    if not url or not url.startswith("http") or is_converted(url):
        return url
    if url in cache:
        return cache[url]
    new_url = url
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200 and 0 < len(resp.content) <= MAX_DOWNLOAD_BYTES:
            new_url = store_image(resp.content, r2_client=r2_client)
        else:
            print(f"    skip (HTTP {resp.status_code}, {len(resp.content)} bytes): {url}")
    except Exception as e:
        print(f"    skip ({type(e).__name__}: {e}): {url}")
    cache[url] = new_url
    return new_url


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write changes (default is a dry run)")
    parser.add_argument("--limit", type=int, default=None, help="maximum number of ads to process")
    parser.add_argument("--ad-id", type=int, default=None, help="only this ad")
    parser.add_argument("--source", choices=["all", "organic", "scraped"], default="all",
                        help="organic = posted by users, scraped = brought in from Facebook")
    args = parser.parse_args()

    r2_client = get_r2_client()
    if args.apply and not r2_client:
        sys.exit("R2 is not configured (R2_ACCESS_KEY_ID / R2_ENDPOINT_URL); nothing to do.")

    db = SessionLocal()
    conditions, params = [], {}
    if args.ad_id:
        conditions.append("id = :ad_id")
        params["ad_id"] = args.ad_id
    if args.source == "organic":
        conditions.append("(source_type IS NULL OR source_type::text = 'ORGANIC_USER')")
    elif args.source == "scraped":
        conditions.append("source_type::text IN ('SCRAPER_BOT', 'SCRAPER')")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = db.execute(
        text(f"SELECT id, image_url, attributes FROM ads {where} ORDER BY id DESC"), params
    ).fetchall()

    processed = changed = images = 0
    for ad_id, image_url, attributes in rows:
        attributes = attributes if isinstance(attributes, dict) else {}
        column_urls, column_is_list = parse_image_url_column(image_url)
        attr_urls = attributes.get("image_urls") if isinstance(attributes.get("image_urls"), list) else []
        attr_urls = [str(u) for u in attr_urls]

        pending = [u for u in dict.fromkeys(column_urls + attr_urls) if u.startswith("http") and not is_converted(u)]
        if not pending:
            continue
        if args.limit is not None and processed >= args.limit:
            break
        processed += 1
        images += len(pending)

        if not args.apply:
            print(f"ad {ad_id}: {len(pending)} image(s) to convert")
            continue

        cache = {}
        # Convert this ad's images in parallel; the lists below then read from the cache
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            for old_url, new_url in zip(pending, executor.map(lambda u: convert(u, r2_client, {}), pending)):
                cache[old_url] = new_url
        new_column_urls = [convert(u, r2_client, cache) for u in column_urls]
        new_attr_urls = [convert(u, r2_client, cache) for u in attr_urls]
        if new_column_urls == column_urls and new_attr_urls == attr_urls:
            continue

        new_image_url = image_url
        if column_urls:
            new_image_url = json.dumps(new_column_urls) if column_is_list else new_column_urls[0]
        new_attributes = dict(attributes)
        if attr_urls:
            new_attributes["image_urls"] = new_attr_urls

        # Raw UPDATE so the ad's updated_at (and its place in the feed) doesn't change
        db.execute(
            text("UPDATE ads SET image_url = :image_url, attributes = CAST(:attributes AS JSONB) WHERE id = :ad_id"),
            {"image_url": new_image_url, "attributes": json.dumps(new_attributes, ensure_ascii=False), "ad_id": ad_id},
        )
        db.commit()
        changed += 1
        for old, new in cache.items():
            if old != new:
                print(f"ad {ad_id}: {old} -> {new}")

    db.close()
    if args.apply:
        print(f"\nDone. {changed} of {processed} ads updated.")
    else:
        print(f"\nDry run: {processed} ads with {images} image(s) would be converted. Re-run with --apply.")


if __name__ == "__main__":
    main()
