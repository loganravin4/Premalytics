"""
=============================================================================
File: config.py
Description: Configuration management for database connections
Author: Premalytics Team
=============================================================================

This module handles loading configuration from environment variables.
Uses python-dotenv to load .env file.

USAGE:
    from config import get_db_config
    
    db_config = get_db_config()
    conn = psycopg2.connect(**db_config)
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import sys

# Load environment variables from .env file
# Look for .env in project root (two levels up from this file)
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / '.env'

# Load .env file if it exists
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
    print(f"✅ Loaded environment variables from: {ENV_FILE}")
else:
    print(f"⚠️  Warning: .env file not found at {ENV_FILE}")
    print("   Using environment variables from system")

def get_db_config() -> dict:
    """
    Get database configuration from environment variables.
    
    Returns:
        dict: Database connection parameters
        
    Raises:
        ValueError: If required environment variables are missing
    """
    # Required environment variables
    required_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
    
    # Check if all required variables are set
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
    
    # Build configuration dictionary
    config = {
        'host': os.getenv('DB_HOST'),
        'port': int(os.getenv('DB_PORT')),
        'database': os.getenv('DB_NAME'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
    }
    
    return config

def get_db_schema() -> str:
    """
    Get database schema name from environment.
    
    Returns:
        str: Schema name (default: 'pl_data')
    """
    return os.getenv('DB_SCHEMA', 'pl_data')

def get_project_root() -> Path:
    """
    Get project root directory.
    
    Returns:
        Path: Project root directory path
    """
    return PROJECT_ROOT

def get_data_dir() -> Path:
    """
    Get data directory path.
    
    Returns:
        Path: Data directory path (PROJECT_ROOT/data/raw)
    """
    return PROJECT_ROOT / 'data-pipeline' / 'data' / 'raw'

# =============================================================================
# Configuration validation on import
# =============================================================================

def validate_config():
    """
    Validate configuration on module import.
    Prints configuration summary (hiding password).
    """
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

# Validate configuration when module is imported
if __name__ != "__main__":
    validate_config()