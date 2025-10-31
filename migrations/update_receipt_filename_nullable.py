"""
Migration: Make receipt filename and file_path nullable
Run this if you want to allow NULL values for filename and file_path
(Since we're not storing files anymore)
"""

from sqlalchemy import text
from database import engine

def migrate():
    """Make filename and file_path nullable in receipts table"""
    with engine.connect() as conn:
        # For MySQL/MariaDB
        try:
            # Make filename nullable
            conn.execute(text("ALTER TABLE receipts MODIFY filename VARCHAR(255) NULL"))
            print("✓ Made filename nullable")
        except Exception as e:
            print(f"Warning: Could not make filename nullable: {e}")
        
        try:
            # Make file_path nullable (should already be, but ensure it)
            conn.execute(text("ALTER TABLE receipts MODIFY file_path VARCHAR(500) NULL"))
            print("✓ Made file_path nullable")
        except Exception as e:
            print(f"Warning: Could not make file_path nullable: {e}")
        
        conn.commit()
        print("✓ Migration completed")

if __name__ == "__main__":
    migrate()

