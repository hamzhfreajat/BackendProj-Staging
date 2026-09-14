import os
import urllib.parse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# Default to the user's provided local environment variables, falling back to local defaults
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
if not DB_PASSWORD:
    raise RuntimeError("CRITICAL: DB_PASSWORD environment variable is not set.")
DB_NAME = os.getenv("DB_NAME", "open")
# Use localhost to connect to the Windows machine's native postgres instance
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

# Safely URL encode password to handle special characters from Coolify auto-generated passwords
encoded_password = urllib.parse.quote_plus(DB_PASSWORD)
SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Globally enforce the exact timezone so the Postgres func.now() strictly outputs Jordan time,
# eliminating the 3-hour "time ago" parsing discrepancy in Flutter.
# NOTE: We disable prepared statements (prepare_threshold=None) because 
# psycopg 3's prepared statements are incompatible with PgBouncer's transaction mode.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={
        "options": "-c timezone=Asia/Amman",
        "prepare_threshold": None
    },
    pool_pre_ping=True,
    pool_recycle=300, # Recycle connections every 5 minutes
    pool_size=5,      # Lowered for staging limits to prevent starvation under load
    max_overflow=10,  # Lowered for staging limits to handle traffic spikes
    pool_timeout=30
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
