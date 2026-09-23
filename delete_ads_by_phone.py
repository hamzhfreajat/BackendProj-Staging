from database import SessionLocal
import models
from sqlalchemy import cast, String

def main():
    db = SessionLocal()
    phone = "0782001546"

    # Find ads matching the phone number in their description or attributes
    # and ensure they are NOT organic
    ads_query = db.query(models.Ad).filter(
        (
            models.Ad.description.like(f'%{phone}%') |
            models.Ad.raw_description.like(f'%{phone}%') |
            cast(models.Ad.attributes, String).like(f'%{phone}%')
        ),
        models.Ad.source_type != models.SourceType.ORGANIC_USER
    )
    
    count = ads_query.count()
    print(f"Found {count} NON-organic ads containing the phone number {phone}.")
    
    if count > 0:
        # Delete the ads
        deleted_count = ads_query.delete(synchronize_session=False)
        db.commit()
        print(f"Successfully deleted {deleted_count} ads.")
    else:
        print("No ads to delete.")

if __name__ == '__main__':
    main()
