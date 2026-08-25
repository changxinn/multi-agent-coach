"""
Database setup script - runs automatically on backend startup.

Creates database, schema, and users table if they don't exist.
"""
import logging
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

logger = logging.getLogger(__name__)


def setup_database(db_url: str, schema_name: str = "systemdb") -> bool:
    """
    Setup database, schema, and users table.
    
    Args:
        db_url: Database connection URL
        schema_name: Schema name to use
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Parse connection URL
        # Format: postgresql+asyncpg://user:pass@host:port/dbname
        db_url_clean = db_url.replace('postgresql+asyncpg://', 'postgresql://')
        
        # Extract database name
        db_name = db_url.split('/')[-1].split('?')[0]
        
        # Connect to PostgreSQL server (default database)
        base_url = '/'.join(db_url_clean.split('/')[:-1]) + '/postgres'
        logger.info(f"Connecting to PostgreSQL server...")
        
        conn = psycopg2.connect(base_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Check if database exists
        cur.execute(sql.SQL("SELECT 1 FROM pg_database WHERE datname = %s"), (db_name,))
        if not cur.fetchone():
            logger.info(f"Creating database: {db_name}")
            cur.execute(sql.SQL(f"CREATE DATABASE {db_name}"))
            logger.info(f"Database '{db_name}' created successfully")
        else:
            logger.info(f"Database '{db_name}' already exists")
        
        cur.close()
        conn.close()
        
        # Connect to target database
        logger.info(f"Connecting to database: {db_name}")
        db_conn = psycopg2.connect(db_url_clean.replace('+asyncpg', ''))
        db_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        db_cur = db_conn.cursor()
        
        # Create schema if not exists
        logger.info(f"Creating schema: {schema_name}")
        db_cur.execute(sql.SQL(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
        
        # Create users table if not exists
        logger.info("Creating users table")
        db_cur.execute(sql.SQL(f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.users (
                id BIGSERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                name VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'USER' 
                    CHECK (role IN ('ADMIN', 'STAFF', 'USER')),
                enabled BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Create index
        db_cur.execute(sql.SQL(f"""
            CREATE INDEX IF NOT EXISTS idx_users_email 
            ON {schema_name}.users(email)
        """))
        
        logger.info("Users table created successfully")
        
        # Grant permissions
        try:
            username = db_url.split('://')[1].split(':')[0]
            db_cur.execute(sql.SQL(f"GRANT ALL PRIVILEGES ON SCHEMA {schema_name} TO {username}"))
            db_cur.execute(sql.SQL(f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA {schema_name} TO {username}"))
            db_cur.execute(sql.SQL(f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {schema_name} TO {username}"))
            logger.info("Permissions granted successfully")
        except Exception as e:
            logger.warning(f"Could not grant permissions: {e}")
        
        db_cur.close()
        db_conn.close()
        
        logger.info("Database setup completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        return False
