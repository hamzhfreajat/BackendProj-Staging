import os
import sys
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding='utf-8')

db_user = 'cmnynjgg70001aumle0zkfovm'
db_password = 'p2j9ggm6cWLAhhVTsbNzYFqKHamzaFraijat'
db_host = 'localhost'
db_port = '5433'
db_name = 'cmnynjgg90003aumlerff4j9q'

DATABASE_URL = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'

ad_ids = [45971, 45870, 42098, 37071, 34555, 23715]
ad_ids_str = ','.join(map(str, ad_ids))

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        ads = conn.execute(text(f"SELECT id, attributes->>'phone' FROM ads WHERE id IN ({ad_ids_str})")).fetchall()
        print('Checking Ads to delete:')
        for ad in ads:
            print(f' - Ad ID {ad[0]}: Phone in attributes = {ad[1]}')
            
        result = conn.execute(text(f'DELETE FROM ads WHERE id IN ({ad_ids_str})'))
        conn.commit()
        print(f'\nSuccessfully deleted {result.rowcount} ads.')
except Exception as e:
    print(f'Query failed: {e}')
