
import os
import pathlib
from dotenv import load_dotenv
from urllib.parse import quote_plus

basedir = pathlib.Path(__file__).parent.parent

# Load env (optional)
load_dotenv()
print("DIRECT TEST:", os.environ.get('DB_HOSTING')) 


print(f"--- ENV CHECK ---")
print(f"Looking for .env in: {basedir}")    

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
    print(f"SECRET_KEY LOADED: {SECRET_KEY}")
    print("ALL ENV VARS WITH DB:")
    for key, val in os.environ.items():
        if 'DB' in key:
            print(f"  {key} = {val}")
    DB_USER = os.environ.get('DB_USER')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    if not DB_PASSWORD:
        raise ValueError("DB_PASSWORD environment variable is not set!")
    DB_HOSTING = os.environ.get('DB_HOSTING')
    DB_PORT = os.environ.get('DB_PORT')
    DB_NAME = os.environ.get('DB_NAME')

    print(f"DB_HOST LOADED: {DB_HOSTING}")  # ✅ will now work

    SAFE_PASSWORD = quote_plus(DB_PASSWORD)

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{SAFE_PASSWORD}@{DB_HOSTING}:{DB_PORT}/{DB_NAME}"
    )

    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "connect_args": {
            "ssl": {
                "ssl_mode": "REQUIRED"   # enforces SSL without needing a cert file
            }
        }
    }


    # OAuth
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

# --- TEST PRINT ---
# This will show up in your terminal when you run 'flask run'
print(f"--- CONFIG CHECK ---")
print(f"DB_NAME LOADED: {Config.DB_NAME}")
print(f"URI CREATED: {Config.SQLALCHEMY_DATABASE_URI[:25]}...")
