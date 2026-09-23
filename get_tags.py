import sys
sys.stdout.reconfigure(encoding='utf-8')
from database import SessionLocal
import models
db = SessionLocal()
tags = db.query(models.Tag).all()
print('Total tags:', len(tags))
for t in tags[:50]:
    cat = getattr(t, 'category_id', 'N/A')
    print(f'Tag ID: {t.id}, Category: {cat}, Name: {t.name}')
