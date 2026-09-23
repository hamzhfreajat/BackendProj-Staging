from database import SessionLocal
import models

def main():
    db = SessionLocal()
    phone = '0782001546'
    user = db.query(models.User).filter(
        (models.User.mobile_number == phone) | 
        (models.User.phone == phone)
    ).first()
    
    if not user:
        print(f"User with phone {phone} not found!")
        return

    print(f"Found user: {user.id} - {user.mobile_number or user.phone}")
    
    ads_to_delete = db.query(models.Ad).filter(
        models.Ad.user_id == user.id,
        models.Ad.source_type != models.SourceType.ORGANIC_USER
    ).all()
    
    print(f"Found {len(ads_to_delete)} scraped ads to delete.")
    
    # Delete them
    for ad in ads_to_delete:
        db.delete(ad)
    
    db.commit()
    print("Deleted successfully.")

if __name__ == '__main__':
    main()
