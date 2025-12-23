#!/usr/bin/env python3
"""
Database migration script to add multitenancy and RBAC support.

This script:
1. Creates the 'organisations' table
2. Creates the 'user_roles' table  
3. Adds 'org_id' column to users, clients, tasks, messages tables
4. Creates a default organization for existing data
5. Assigns org_id to all existing records
6. Makes org_id NOT NULL after data migration
7. Adds indexes for performance

Run this script BEFORE starting the updated server.
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../.env'))

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL not found in environment variables")
    sys.exit(1)

print(f"🔗 Connecting to database...")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def run_migration():
    """Execute the migration steps"""
    session = Session()
    
    try:
        print("\n" + "="*60)
        print("MULTITENANCY & RBAC MIGRATION")
        print("="*60 + "\n")
        
        # Step 1: Create organisations table
        print("📋 Step 1: Creating 'organisations' table...")
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS organisations (
                id SERIAL PRIMARY KEY,
                name VARCHAR(150) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        session.commit()
        print("✅ organisations table created\n")
        
        # Step 2: Create user_roles table
        print("📋 Step 2: Creating 'user_roles' table...")
        session.execute(text("""
            DO $$ BEGIN
                CREATE TYPE role_enum AS ENUM ('owner', 'manager', 'employee', 'intern');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS user_roles (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                org_id INTEGER NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
                role role_enum NOT NULL DEFAULT 'intern',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, org_id)
            );
        """))
        session.commit()
        print("✅ user_roles table created\n")
        
        # Step 3: Add org_id columns (nullable initially)
        print("📋 Step 3: Adding org_id columns to existing tables...")
        
        # Check if org_id already exists before adding
        for table in ['users', 'clients', 'tasks', 'messages']:
            result = session.execute(text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='{table}' AND column_name='org_id';
            """)).fetchone()
            
            if not result:
                print(f"   Adding org_id to {table}...")
                session.execute(text(f"""
                    ALTER TABLE {table} 
                    ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organisations(id);
                """))
            else:
                print(f"   org_id already exists in {table}, skipping...")
        
        session.commit()
        print("✅ org_id columns added\n")
        
        # Step 4: Create default organization if data exists
        print("📋 Step 4: Creating default organisation for existing data...")
        
        # Check if any users exist
        result = session.execute(text("SELECT COUNT(*) FROM users;")).fetchone()
        user_count = result[0] if result else 0
        
        if user_count > 0:
            print(f"   Found {user_count} existing users")
            
            # Check if default org already exists
            result = session.execute(text("""
                SELECT id FROM organisations WHERE name = 'Default Organisation';
            """)).fetchone()
            
            if result:
                default_org_id = result[0]
                print(f"   Default organisation already exists (id={default_org_id})")
            else:
                # Create default organization
                result = session.execute(text("""
                    INSERT INTO organisations (name, created_at, updated_at)
                    VALUES ('Default Organisation', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    RETURNING id;
                """))
                default_org_id = result.fetchone()[0]
                session.commit()
                print(f"   ✅ Created 'Default Organisation' (id={default_org_id})")
            
            # Step 5: Assign org_id to all existing records
            print("📋 Step 5: Assigning org_id to existing records...")
            
            for table in ['users', 'clients', 'tasks', 'messages']:
                result = session.execute(text(f"""
                    UPDATE {table} 
                    SET org_id = {default_org_id} 
                    WHERE org_id IS NULL;
                """))
                updated = result.rowcount
                print(f"   Updated {updated} records in {table}")
            
            session.commit()
            
            # Assign Owner role to first user in default org
            print("📋 Step 6: Assigning Owner role to first user...")
            result = session.execute(text("""
                SELECT id FROM users WHERE org_id = :org_id ORDER BY created_at ASC LIMIT 1;
            """), {"org_id": default_org_id}).fetchone()
            
            if result:
                first_user_id = result[0]
                
                # Check if role already assigned
                role_exists = session.execute(text("""
                    SELECT id FROM user_roles WHERE user_id = :user_id AND org_id = :org_id;
                """), {"user_id": first_user_id, "org_id": default_org_id}).fetchone()
                
                if not role_exists:
                    session.execute(text("""
                        INSERT INTO user_roles (user_id, org_id, role, created_at)
                        VALUES (:user_id, :org_id, 'owner', CURRENT_TIMESTAMP);
                    """), {"user_id": first_user_id, "org_id": default_org_id})
                    print(f"   ✅ Assigned Owner role to user {first_user_id}")
                else:
                    print(f"   Role already assigned to user {first_user_id}")
                
                # Assign Intern role to all other users
                session.execute(text("""
                    INSERT INTO user_roles (user_id, org_id, role, created_at)
                    SELECT id, org_id, 'intern', CURRENT_TIMESTAMP
                    FROM users
                    WHERE id != :first_user_id 
                        AND org_id = :org_id
                        AND NOT EXISTS (
                            SELECT 1 FROM user_roles 
                            WHERE user_roles.user_id = users.id 
                            AND user_roles.org_id = users.org_id
                        );
                """), {"first_user_id": first_user_id, "org_id": default_org_id})
                session.commit()
                print(f"   ✅ Assigned Intern role to other users")
            
            print("✅ Data migration complete\n")
        else:
            print("   No existing data to migrate\n")
        
        # Step 7: Make org_id NOT NULL
        print("📋 Step 7: Making org_id columns NOT NULL...")
        for table in ['users', 'clients', 'tasks', 'messages']:
            session.execute(text(f"""
                ALTER TABLE {table} 
                ALTER COLUMN org_id SET NOT NULL;
            """))
        session.commit()
        print("✅ org_id columns set to NOT NULL\n")
        
        # Step 8: Create indexes for performance
        print("📋 Step 8: Creating indexes...")
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_org_id ON users(org_id);",
            "CREATE INDEX IF NOT EXISTS idx_clients_org_id ON clients(org_id);",
            "CREATE INDEX IF NOT EXISTS idx_tasks_org_id ON tasks(org_id);",
            "CREATE INDEX IF NOT EXISTS idx_messages_org_id ON messages(org_id);",
            "CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_user_roles_org_id ON user_roles(org_id);",
        ]
        
        for idx_sql in indexes:
            session.execute(text(idx_sql))
        session.commit()
        print("✅ Indexes created\n")
        
        print("="*60)
        print("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
        print("="*60 + "\n")
        
        # Show summary
        org_count = session.execute(text("SELECT COUNT(*) FROM organisations;")).fetchone()[0]
        role_count = session.execute(text("SELECT COUNT(*) FROM user_roles;")).fetchone()[0]
        
        print("📊 Summary:")
        print(f"   Organisations: {org_count}")
        print(f"   User Roles: {role_count}")
        print()
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ ERROR during migration: {e}")
        print("\n⚠️  Migration failed. Database rolled back.")
        sys.exit(1)
    finally:
        session.close()

def rollback_migration():
    """Rollback the migration (use with caution!)"""
    print("\n⚠️  WARNING: This will remove all multitenancy data!")
    response = input("Type 'ROLLBACK' to confirm: ")
    
    if response != "ROLLBACK":
        print("Rollback cancelled.")
        return
    
    session = Session()
    try:
        print("\n🔄 Rolling back migration...")
        
        # Drop indexes
        session.execute(text("DROP INDEX IF EXISTS idx_users_org_id CASCADE;"))
        session.execute(text("DROP INDEX IF EXISTS idx_clients_org_id CASCADE;"))
        session.execute(text("DROP INDEX IF EXISTS idx_tasks_org_id CASCADE;"))
        session.execute(text("DROP INDEX IF EXISTS idx_messages_org_id CASCADE;"))
        session.execute(text("DROP INDEX IF EXISTS idx_user_roles_user_id CASCADE;"))
        session.execute(text("DROP INDEX IF EXISTS idx_user_roles_org_id CASCADE;"))
        
        # Remove org_id columns
        for table in ['users', 'clients', 'tasks', 'messages']:
            session.execute(text(f"ALTER TABLE {table} DROP COLUMN IF EXISTS org_id CASCADE;"))
        
        # Drop tables
        session.execute(text("DROP TABLE IF EXISTS user_roles CASCADE;"))
        session.execute(text("DROP TABLE IF EXISTS organisations CASCADE;"))
        session.execute(text("DROP TYPE IF EXISTS role_enum CASCADE;"))
        
        session.commit()
        print("✅ Rollback complete")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ ERROR during rollback: {e}")
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        rollback_migration()
    else:
        run_migration()
