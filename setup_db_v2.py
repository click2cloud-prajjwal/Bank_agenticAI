# setup_db_v2_fixed.py
# Fixed database setup with proper foreign key constraints (NO CASCADE CYCLES)
# WARNING: This uses PLAIN TEXT MPINs for development only!
# MUST implement bcrypt hashing before production deployment!

import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()

SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DATABASE = os.getenv("SQL_DATABASE")
SQL_DRIVER = os.getenv("SQL_DRIVER", "ODBC Driver 17 for SQL Server")
SQL_TRUSTED = os.getenv("SQL_TRUSTED_CONNECTION", "No")
SQL_USERNAME = os.getenv("SQL_USERNAME")
SQL_PASSWORD = os.getenv("SQL_PASSWORD")

def get_master_connection():
    """Connect to master database to create new database"""
    if SQL_TRUSTED.lower() == "yes":
        conn_str = (
            f"DRIVER={{{SQL_DRIVER}}};"
            f"SERVER={SQL_SERVER};"
            f"DATABASE=master;"
            f"Trusted_Connection=yes;"
        )
    else:
        conn_str = (
            f"DRIVER={{{SQL_DRIVER}}};"
            f"SERVER={SQL_SERVER};"
            f"DATABASE=master;"
            f"UID={SQL_USERNAME};"
            f"PWD={SQL_PASSWORD};"
        )
    return pyodbc.connect(conn_str, autocommit=True)

def get_connection():
    """Connect to BankData_v2 database"""
    if SQL_TRUSTED.lower() == "yes":
        conn_str = (
            f"DRIVER={{{SQL_DRIVER}}};"
            f"SERVER={SQL_SERVER};"
            f"DATABASE={SQL_DATABASE};"
            f"Trusted_Connection=yes;"
        )
    else:
        conn_str = (
            f"DRIVER={{{SQL_DRIVER}}};"
            f"SERVER={SQL_SERVER};"
            f"DATABASE={SQL_DATABASE};"
            f"UID={SQL_USERNAME};"
            f"PWD={SQL_PASSWORD};"
        )
    return pyodbc.connect(conn_str)

def create_database():
    """Create BankData_v2 database if it doesn't exist"""
    print(f"📦 Checking database '{SQL_DATABASE}'...")
    
    conn = get_master_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"""
            IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = '{SQL_DATABASE}')
            BEGIN
                CREATE DATABASE {SQL_DATABASE};
            END
        """)
        print(f"✅ Database '{SQL_DATABASE}' ready\n")
    except Exception as e:
        print(f"⚠️  Database check: {e}")
    finally:
        cursor.close()
        conn.close()

def drop_existing_tables():
    """Drop existing tables if they exist (for clean setup)"""
    print("🗑️  Dropping existing tables for clean setup...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Drop in reverse order of dependencies
    tables_to_drop = [
        'audit_log',
        'sessions', 
        'spending_analytics',
        'user_liabilities',
        'user_income',
        'user_identity',
        'transactions',
        'accounts',
        'users'
    ]
    
    for table in tables_to_drop:
        try:
            cursor.execute(f"""
                IF EXISTS (SELECT * FROM sys.objects WHERE name='{table}' AND type='U')
                BEGIN
                    DROP TABLE {table};
                END
            """)
            conn.commit()
            print(f"  Dropped: {table}")
        except Exception as e:
            print(f"  ⚠️  {table}: {e}")
    
    cursor.close()
    conn.close()
    print("✅ Tables cleared\n")

def create_tables():
    """Create all tables with proper foreign key constraints"""
    print("📦 Creating tables...\n")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # ============================================
        # 1. USERS TABLE - Core Authentication
        # ============================================
        print("  Creating users table...")
        cursor.execute("""
            CREATE TABLE users (
                phone NVARCHAR(20) PRIMARY KEY,
                mpin NVARCHAR(10) NOT NULL,
                name NVARCHAR(255),
                email NVARCHAR(255) UNIQUE,
                is_active BIT DEFAULT 1,
                failed_login_attempts INT DEFAULT 0,
                last_login DATETIME2,
                created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
                updated_at DATETIME2 DEFAULT SYSUTCDATETIME()
            );
        """)
        conn.commit()
        print("    ✅ users")
        
        # ============================================
        # 2. ACCOUNTS TABLE
        # ============================================
        print("  Creating accounts table...")
        cursor.execute("""
            CREATE TABLE accounts (
                account_number BIGINT PRIMARY KEY,
                phone NVARCHAR(20) NOT NULL,
                name NVARCHAR(255),
                type NVARCHAR(60),
                subtype NVARCHAR(60),
                mask NVARCHAR(10),
                currency NVARCHAR(10) DEFAULT 'USD',
                balance_available DECIMAL(18,2),
                balance_current DECIMAL(18,2),
                is_primary BIT DEFAULT 0,
                status NVARCHAR(20) DEFAULT 'active',
                created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
                updated_at DATETIME2 DEFAULT SYSUTCDATETIME(),
                CONSTRAINT FK_accounts_users FOREIGN KEY (phone) 
                    REFERENCES users(phone) ON DELETE CASCADE
            );
        """)
        conn.commit()
        print("    ✅ accounts")
        
        # ============================================
        # 3. TRANSACTIONS TABLE
        # FIX: Remove CASCADE from phone FK to avoid cycle
        # ============================================
        print("  Creating transactions table...")
        cursor.execute("""
            CREATE TABLE transactions (
                transaction_id BIGINT PRIMARY KEY,
                account_number BIGINT NOT NULL,
                phone NVARCHAR(20) NOT NULL,
                name NVARCHAR(255),
                amount DECIMAL(18,2),
                date DATE,
                category NVARCHAR(500),
                merchant_name NVARCHAR(255),
                pending BIT DEFAULT 0,
                currency NVARCHAR(10) DEFAULT 'USD',
                created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
                CONSTRAINT FK_transactions_accounts FOREIGN KEY (account_number) 
                    REFERENCES accounts(account_number) ON DELETE CASCADE,
                CONSTRAINT FK_transactions_users FOREIGN KEY (phone) 
                    REFERENCES users(phone) ON DELETE NO ACTION
            );
        """)
        conn.commit()
        print("    ✅ transactions")
        
        # ============================================
        # 4. USER_IDENTITY TABLE
        # ============================================
        print("  Creating user_identity table...")
        cursor.execute("""
            CREATE TABLE user_identity (
                phone NVARCHAR(20) PRIMARY KEY,
                full_name NVARCHAR(255),
                email NVARCHAR(255),
                date_of_birth DATE,
                address_street NVARCHAR(500),
                address_city NVARCHAR(100),
                address_state NVARCHAR(50),
                address_zip NVARCHAR(20),
                address_country NVARCHAR(50),
                created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
                updated_at DATETIME2 DEFAULT SYSUTCDATETIME(),
                CONSTRAINT FK_identity_users FOREIGN KEY (phone) 
                    REFERENCES users(phone) ON DELETE CASCADE
            );
        """)
        conn.commit()
        print("    ✅ user_identity")
        
        # ============================================
        # 5. USER_INCOME TABLE
        # ============================================
        print("  Creating user_income table...")
        cursor.execute("""
            CREATE TABLE user_income (
                income_id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
                phone NVARCHAR(20) NOT NULL,
                account_number BIGINT,
                employer_name NVARCHAR(255),
                monthly_income DECIMAL(18,2),
                annual_income DECIMAL(18,2),
                pay_frequency NVARCHAR(50),
                last_payment_date DATE,
                last_payment_amount DECIMAL(18,2),
                confidence DECIMAL(5,2),
                created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
                CONSTRAINT FK_income_users FOREIGN KEY (phone) 
                    REFERENCES users(phone) ON DELETE CASCADE,
                CONSTRAINT FK_income_accounts FOREIGN KEY (account_number) 
                    REFERENCES accounts(account_number) ON DELETE NO ACTION
            );
        """)
        conn.commit()
        print("    ✅ user_income")
        
        # ============================================
        # 6. USER_LIABILITIES TABLE
        # ============================================
        print("  Creating user_liabilities table...")
        cursor.execute("""
            CREATE TABLE user_liabilities (
                liability_number BIGINT PRIMARY KEY,
                phone NVARCHAR(20) NOT NULL,
                liability_type NVARCHAR(50),
                balance DECIMAL(18,2),
                apr DECIMAL(5,2),
                minimum_payment DECIMAL(18,2),
                credit_limit DECIMAL(18,2),
                last_payment_amount DECIMAL(18,2),
                last_payment_date DATE,
                origination_date DATE,
                maturity_date DATE,
                loan_term INT,
                loan_status NVARCHAR(50),
                created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
                CONSTRAINT FK_liabilities_users FOREIGN KEY (phone) 
                    REFERENCES users(phone) ON DELETE CASCADE
            );
        """)
        conn.commit()
        print("    ✅ user_liabilities")
        
        # ============================================
        # 7. SPENDING_ANALYTICS TABLE
        # ============================================
        print("  Creating spending_analytics table...")
        cursor.execute("""
            CREATE TABLE spending_analytics (
                analytics_id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
                phone NVARCHAR(20) NOT NULL,
                account_number BIGINT,
                month DATE NOT NULL,
                total_income DECIMAL(18,2),
                total_expenses DECIMAL(18,2),
                net_cash_flow DECIMAL(18,2),
                top_category NVARCHAR(100),
                top_category_amount DECIMAL(18,2),
                transaction_count INT,
                avg_transaction_amount DECIMAL(18,2),
                created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
                CONSTRAINT FK_analytics_users FOREIGN KEY (phone) 
                    REFERENCES users(phone) ON DELETE CASCADE,
                CONSTRAINT FK_analytics_accounts FOREIGN KEY (account_number) 
                    REFERENCES accounts(account_number) ON DELETE NO ACTION
            );
        """)
        conn.commit()
        print("    ✅ spending_analytics")
        
        # ============================================
        # 8. SESSIONS TABLE
        # ============================================
        print("  Creating sessions table...")
        cursor.execute("""
            CREATE TABLE sessions (
                session_id NVARCHAR(255) PRIMARY KEY,
                phone NVARCHAR(20) NOT NULL,
                selected_account BIGINT,
                ip_address NVARCHAR(50),
                user_agent NVARCHAR(500),
                created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
                expires_at DATETIME2,
                last_activity DATETIME2 DEFAULT SYSUTCDATETIME(),
                CONSTRAINT FK_sessions_users FOREIGN KEY (phone) 
                    REFERENCES users(phone) ON DELETE CASCADE
            );
        """)
        conn.commit()
        print("    ✅ sessions")
        
        # ============================================
        # 9. AUDIT_LOG TABLE (No FK - for data retention)
        # ============================================
        print("  Creating audit_log table...")
        cursor.execute("""
            CREATE TABLE audit_log (
                log_id BIGINT IDENTITY(1,1) PRIMARY KEY,
                phone NVARCHAR(20),
                action_type NVARCHAR(50),
                details NVARCHAR(MAX),
                ip_address NVARCHAR(50),
                created_at DATETIME2 DEFAULT SYSUTCDATETIME()
            );
        """)
        conn.commit()
        print("    ✅ audit_log")
        
        print("\n✅ All tables created successfully!\n")
        
    except Exception as e:
        print(f"\n❌ Error creating tables: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

def create_indexes():
    """Create indexes for performance"""
    print("⚡ Creating indexes...\n")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    indexes = [
        ("idx_users_email", "users", "email"),
        ("idx_users_active", "users", "is_active"),
        ("idx_accounts_phone", "accounts", "phone"),
        ("idx_accounts_status", "accounts", "status"),
        ("idx_accounts_primary", "accounts", "is_primary"),
        ("idx_transactions_account", "transactions", "account_number"),
        ("idx_transactions_phone", "transactions", "phone"),
        ("idx_transactions_date", "transactions", "date DESC"),
        ("idx_transactions_pending", "transactions", "pending"),
        ("idx_income_phone", "user_income", "phone"),
        ("idx_liabilities_phone", "user_liabilities", "phone"),
        ("idx_analytics_phone", "spending_analytics", "phone"),
        ("idx_analytics_month", "spending_analytics", "month DESC"),
        ("idx_sessions_phone", "sessions", "phone"),
        ("idx_sessions_expires", "sessions", "expires_at"),
        ("idx_audit_phone", "audit_log", "phone"),
        ("idx_audit_action", "audit_log", "action_type"),
        ("idx_audit_created", "audit_log", "created_at DESC"),
    ]
    
    for idx_name, table_name, columns in indexes:
        try:
            cursor.execute(f"""
                IF NOT EXISTS (SELECT name FROM sys.indexes WHERE name='{idx_name}')
                BEGIN
                    CREATE INDEX {idx_name} ON {table_name}({columns});
                END
            """)
            conn.commit()
            print(f"  ✅ {idx_name}")
        except Exception as e:
            print(f"  ⚠️  {idx_name}: {e}")
    
    cursor.close()
    conn.close()
    print("\n✅ Indexes created!\n")

def insert_sample_data():
    """Insert sample test user for development"""
    print("👤 Creating sample test user...\n")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Sample user
        cursor.execute("""
            IF NOT EXISTS (SELECT phone FROM users WHERE phone = '+15551234567')
            BEGIN
                INSERT INTO users (phone, mpin, name, email, created_at)
                VALUES ('+15551234567', '0000', 'Test User', 'test@example.com', SYSUTCDATETIME())
            END
        """)
        
        # Sample checking account
        cursor.execute("""
            IF NOT EXISTS (SELECT account_number FROM accounts WHERE account_number = 1234567890123456)
            BEGIN
                INSERT INTO accounts (
                    account_number, phone, name, type, subtype, 
                    mask, balance_available, balance_current, is_primary, status
                )
                VALUES (
                    1234567890123456, '+15551234567', 'Primary Checking', 'depository', 'checking',
                    '3456', 2500.00, 2500.00, 1, 'active'
                )
            END
        """)
        
        # Sample savings account
        cursor.execute("""
            IF NOT EXISTS (SELECT account_number FROM accounts WHERE account_number = 2345678901234567)
            BEGIN
                INSERT INTO accounts (
                    account_number, phone, name, type, subtype,
                    mask, balance_available, balance_current, is_primary, status
                )
                VALUES (
                    2345678901234567, '+15551234567', 'Savings Account', 'depository', 'savings',
                    '4567', 10000.00, 10000.00, 0, 'active'
                )
            END
        """)
        
        # Sample identity
        cursor.execute("""
            IF NOT EXISTS (SELECT phone FROM user_identity WHERE phone = '+15551234567')
            BEGIN
                INSERT INTO user_identity (
                    phone, full_name, email, address_city, address_state, address_country
                )
                VALUES (
                    '+15551234567', 'Test User', 'test@example.com', 'San Francisco', 'CA', 'USA'
                )
            END
        """)
        
        conn.commit()
        
        print("  ✅ Test user created:")
        print("     Phone: +15551234567")
        print("     MPIN: 0000")
        print("     Accounts: 2 (Checking + Savings)")
        print("     Total Balance: $12,500\n")
        
    except Exception as e:
        print(f"  ⚠️  Sample data: {e}\n")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def verify_setup():
    """Verify database setup"""
    print("🔍 Verifying setup...\n")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    tables = [
        'users', 'accounts', 'transactions', 'user_identity',
        'user_income', 'user_liabilities', 'spending_analytics',
        'sessions', 'audit_log'
    ]
    
    all_good = True
    
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  ✅ {table:25} {count:>5} records")
        except Exception as e:
            print(f"  ❌ {table:25} ERROR: {str(e)[:50]}")
            all_good = False
    
    cursor.close()
    conn.close()
    
    return all_good

def run():
    print("\n" + "="*70)
    print("🚀 CREATING NEW DATABASE SCHEMA (BankData_v2)")
    print("="*70)
    print("⚠️  WARNING: PLAIN TEXT MPINs - DEVELOPMENT ONLY!")
    print("="*70 + "\n")

    try:
        # Step 1: Create database
        create_database()

        # Step 2: Drop existing tables for clean setup
        try:
            drop_existing_tables()
        except:
            print("⚠️  No existing tables to drop (first run)\n")

        # Step 3: Create tables (clean, empty)
        create_tables()

        # Step 4: Create indexes
        create_indexes()

        # ⚠️ IMPORTANT: No sample data, clean DB for migration
        print("\n🚫 Skipping sample data insert (clean migration mode)\n")

        # Step 5: Verify
        if verify_setup():
            print("\n" + "="*70)
            print("✅ DATABASE SETUP COMPLETE!")
            print("="*70)
            print(f"\nDatabase: {SQL_DATABASE}")
            print("Structure: Phone-based authentication")
            print("MPIN: Plain text (⚠️ DEVELOPMENT ONLY)")
            print("\n⚠️  NEXT STEPS:")
            print("   1. Update .env → SQL_DATABASE=BankData_v2")
            print("   2. Run migrate_data_to_v2.py to import real data")
            print("   3. Test login using imported user phone numbers")
            print("\n📝 Foreign Key Strategy:")
            print("   - users → accounts: CASCADE DELETE")
            print("   - accounts → transactions: CASCADE DELETE")
            print("   - users → transactions: NO ACTION (avoid cascade cycle)")
            print("="*70 + "\n")
        else:
            print("\n⚠️  Setup completed with some errors. Check logs above.\n")

    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run()