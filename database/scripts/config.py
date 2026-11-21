"""Database connection settings loaded from the project .env."""

import os
from pathlib import Path
from dotenv import load_dotenv
import sys

PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / '.env'

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
    print(f"✅ Loaded environment variables from: {ENV_FILE}")
else:
    print(f"⚠️  Warning: .env file not found at {ENV_FILE}")
    print("   Using environment variables from system")

def get_db_config() -> dict:
    required_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("\n📝 Please create a .env file in the project root with:")
        print("   DB_HOST=localhost")
        print("   DB_PORT=5432")
        print("   DB_NAME=premalytics_db")
        print("   DB_USER=postgres")
        print("   DB_PASSWORD=your_password")
        sys.exit(1)
    
    config = {
        'host': os.getenv('DB_HOST'),
        'port': int(os.getenv('DB_PORT')),
        'database': os.getenv('DB_NAME'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
    }
    
    return config

def get_db_schema() -> str:
    return os.getenv('DB_SCHEMA', 'pl_data')

def get_project_root() -> Path:
    return PROJECT_ROOT

def get_data_dir() -> Path:
    return PROJECT_ROOT / 'data-pipeline' / 'data' / 'raw'


def validate_config():
    try:
        config = get_db_config()
        schema = get_db_schema()
        
        print("\n" + "="*70)
        print("📋 DATABASE CONFIGURATION")
        print("="*70)
        print(f"Host:     {config['host']}")
        print(f"Port:     {config['port']}")
        print(f"Database: {config['database']}")
        print(f"User:     {config['user']}")
        print(f"Schema:   {schema}")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Configuration Error: {e}\n")
        sys.exit(1)

if __name__ != "__main__":
    validate_config()