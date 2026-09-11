import os
import sys

# Add backend dir to path so we can import models
sys.path.append('d:/open/classifieds-app-staging-backend')
from models import Ad
from database import SessionLocal

db = SessionLocal()

def main():
    print("Starting floor migration...")
    ads = db.query(Ad).all()
    updated_count = 0
    
    for ad in ads:
        title = ad.title or ""
        desc = ad.description or ""
        text = (title + " " + desc).lower()
        
        # Determine the floor type based on keywords
        new_floor = None
        if "طابق اخير مع روف" in text or "طابق أخير مع روف" in text:
            new_floor = "طابق أخير مع روف"
        elif "روف" in text:
            new_floor = "روف"
        elif "طابق اخير" in text or "طابق أخير" in text:
            new_floor = "طابق أخير"
            
        if new_floor:
            # Init attributes if it doesn't exist
            if not ad.attributes:
                ad.attributes = {}
            
            # Update only if it doesn't already have this exact floor
            current_floor = ad.attributes.get("floor")
            if current_floor != new_floor:
                # Update attributes dictionary and flag it as modified
                # We need to make sure SQLAlchemy detects the JSONB update
                # Re-assigning a new dict does this.
                new_attrs = dict(ad.attributes)
                new_attrs["floor"] = new_floor
                ad.attributes = new_attrs
                updated_count += 1
                print(f"Ad {ad.id}: Set floor to '{new_floor}'")

    if updated_count > 0:
        db.commit()
        print(f"Migration completed. {updated_count} ads updated.")
    else:
        print("No ads needed updating.")

if __name__ == "__main__":
    main()
