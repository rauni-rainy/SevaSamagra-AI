import sqlalchemy as sa
from .connection import engine

def initialize_database():
    """
    Called on startup to ensure PostGIS and other extensions exist.
    """
    with engine.connect() as conn:
        # Create PostGIS extension if it doesn't exist
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()
