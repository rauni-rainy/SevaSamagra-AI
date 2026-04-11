import os
import sys
from sqlalchemy import text

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.connection import engine

def migrate():
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE volunteer_assignments ADD COLUMN points_awarded INTEGER DEFAULT 0;"))
            print("Added points_awarded column.")
        except Exception as e:
            print("points_awarded might already exist:", e)
            
        try:
            conn.execute(text("ALTER TABLE volunteer_assignments ADD COLUMN feedback_comment TEXT;"))
            print("Added feedback_comment column.")
        except Exception as e:
            print("feedback_comment might already exist:", e)

if __name__ == "__main__":
    migrate()
