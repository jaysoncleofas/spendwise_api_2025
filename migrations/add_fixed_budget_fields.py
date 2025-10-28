"""
Migration: Add fixed budget fields to categories table
Date: 2025-10-26
Description: Adds budget_type, budget_start_date, and fixed_budget_spent fields to support fixed budgets
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text
from database import engine

def upgrade():
    """Add new budget fields to categories table"""
    
    with engine.connect() as conn:
        # Add budget_type column
        conn.execute(text("""
            ALTER TABLE categories 
            ADD COLUMN budget_type VARCHAR(20) DEFAULT 'monthly'
        """))
        
        # Add budget_start_date column
        conn.execute(text("""
            ALTER TABLE categories 
            ADD COLUMN budget_start_date DATETIME NULL
        """))
        
        # Add fixed_budget_spent column
        conn.execute(text("""
            ALTER TABLE categories 
            ADD COLUMN fixed_budget_spent FLOAT DEFAULT 0.0
        """))
        
        conn.commit()
    
    print("✅ Migration completed: Added budget_type, budget_start_date, and fixed_budget_spent columns to categories table")

def downgrade():
    """Remove budget fields from categories table"""
    
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE categories DROP COLUMN budget_type"))
        conn.execute(text("ALTER TABLE categories DROP COLUMN budget_start_date"))
        conn.execute(text("ALTER TABLE categories DROP COLUMN fixed_budget_spent"))
        conn.commit()
    
    print("✅ Downgrade completed: Removed budget fields from categories table")

if __name__ == "__main__":
    print("Running migration: Add fixed budget fields")
    upgrade()

