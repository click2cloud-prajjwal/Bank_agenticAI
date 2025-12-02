# migrate_data_to_v2.py
# Migrate data from BankData (old) to BankData_v2 (new structure)

import pyodbc
import os
import random
import time
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DRIVER = os.getenv("SQL_DRIVER", "ODBC Driver 17 for SQL Server")
SQL_TRUSTED = os.getenv("SQL_TRUSTED_CONNECTION", "No")
SQL_USERNAME = os.getenv("SQL_USERNAME")
SQL_PASSWORD = os.getenv("SQL_PASSWORD")

# Account number mapping (old UUID -> new readable number)
account_mapping = {}
transaction_id_counter = int(datetime.now().strftime("%Y%m%d")) * 100000000

def get_connection(database):
    """Connect to specified database"""
    if SQL_TRUSTED.lower() == "yes":
        conn_str = (
            f"DRIVER={{{SQL_DRIVER}}};"
            f"SERVER={SQL_SERVER};"
            f"DATABASE={database};"
            f"Trusted_Connection=yes;"
        )
    else:
        conn_str = (
            f"DRIVER={{{SQL_DRIVER}}};"
            f"SERVER={SQL_SERVER};"
            f"DATABASE={database};"
            f"UID={SQL_USERNAME};PWD={SQL_PASSWORD};"
        )
    return pyodbc.connect(conn_str)

def generate_account_number(account_type="checking"):
    """Generate readable 16-digit account number"""
    # First digit based on type
    if "checking" in account_type.lower():
        prefix = "1"
    elif "savings" in account_type.lower():
        prefix = "2"
    elif "credit" in account_type.lower():
        prefix = "4"
    else:
        prefix = "3"
    
    # Generate rest of digits
    rest = str(random.randint(100000000000000, 999999999999999))
    return int(prefix + rest)

def generate_transaction_id():
    """Generate readable transaction ID"""
    global transaction_id_counter
    transaction_id_counter += 1
    return transaction_id_counter

def generate_liability_number(liability_type):
    """Generate liability account number"""
    if 'credit' in liability_type.lower():
        return random.randint(4000000000000000, 4999999999999999)
    elif 'mortgage' in liability_type.lower():
        return random.randint(5000000000000000, 5999999999999999)
    else:
        return random.randint(6000000000000000, 6999999999999999)

def migrate_users():
    print("\n" + "="*60)
    print("📱 STEP 1: Migrating Users")
    print("="*60)

    old = get_connection("BankData").cursor()
    new_conn = get_connection("BankData_v2")
    new = new_conn.cursor()

    old.execute("""
        SELECT DISTINCT phone, full_name, email
        FROM user_identity
        WHERE phone IS NOT NULL
    """)
    users = old.fetchall()
    print(f"\nFound {len(users)} users to migrate...\n")

    for phone, name, email in users:
        try:
            # Fix duplicate/NULL emails automatically
            safe_email = email
            if not safe_email or safe_email.lower().startswith("accountholder"):
                safe_email = f"{phone}@autogen.local"

            # Avoid inserting duplicates
            new.execute("SELECT phone FROM users WHERE phone = ?", (phone,))
            if new.fetchone():
                print(f"⚠️ User {phone} exists, skipping…")
                continue

            new.execute("""
                INSERT INTO users (phone, mpin, name, email, created_at)
                VALUES (?, '0000', ?, ?, SYSUTCDATETIME())
            """, (phone, name or f"User {phone[-4:]}", safe_email))

            print(f"✅ Migrated user: {phone}")
        except Exception as e:
            print(f"❌ User migration error for {phone}: {e}")

    new_conn.commit()
    print("\n✅ Users migrated with auto-fixed emails\n")
    migrated_count = len(users)
    print(f"\n✅ Migrated {migrated_count} users")
    print(f"   Default MPIN: 0000 (all users)")
    old.close()
    new.close()
    new_conn.close()

def migrate_accounts():
    """Migrate accounts with new account numbers"""
    print("\n" + "="*60)
    print("🏦 STEP 2: Migrating Accounts")
    print("="*60)
    
    old_conn = get_connection("BankData")
    new_conn = get_connection("BankData_v2")
    
    old_cursor = old_conn.cursor()
    new_cursor = new_conn.cursor()
    
    # Get accounts with their phone numbers
    old_cursor.execute("""
        SELECT 
            a.account_id,
            a.name,
            a.type,
            a.subtype,
            a.mask,
            a.currency,
            a.balance_available,
            a.balance_current,
            ui.phone
        FROM accounts a
        LEFT JOIN items i ON a.item_id = i.item_id
        LEFT JOIN user_identity ui ON i.item_id = ui.item_id
        WHERE ui.phone IS NOT NULL
    """)
    
    accounts = old_cursor.fetchall()
    migrated_count = 0
    
    print(f"\nFound {len(accounts)} accounts to migrate...\n")
    
    for old_account_id, name, acc_type, subtype, mask, currency, avail, current, phone in accounts:
        try:
            # Generate new account number
            new_account_number = generate_account_number(subtype or "checking")
            
            # Store mapping for transactions
            account_mapping[str(old_account_id)] = new_account_number
            
            # Insert account
            new_cursor.execute("""
                INSERT INTO accounts (
                    account_number, phone, name, type, subtype,
                    mask, currency, balance_available, balance_current,
                    is_primary, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', SYSUTCDATETIME())
            """, (
                new_account_number, phone, name, acc_type, subtype,
                mask, currency or 'USD', 
                float(avail) if avail else 0,
                float(current) if current else 0,
                1 if migrated_count == 0 else 0  # First account is primary
            ))
            
            migrated_count += 1
            print(f"✅ Migrated account: {name} ({mask}) -> {new_account_number}")
            
        except Exception as e:
            print(f"❌ Error migrating account {name}: {e}")
    
    new_conn.commit()
    
    print(f"\n✅ Migrated {migrated_count} accounts")
    print(f"   Account number range: 1000000000000000 - 9999999999999999")
    
    old_cursor.close()
    new_cursor.close()
    old_conn.close()
    new_conn.close()

def migrate_transactions():
    """Migrate transactions to new structure"""
    print("\n" + "="*60)
    print("💳 STEP 3: Migrating Transactions")
    print("="*60)
    
    old_conn = get_connection("BankData")
    new_conn = get_connection("BankData_v2")
    
    old_cursor = old_conn.cursor()
    new_cursor = new_conn.cursor()
    
    # Get transactions
    old_cursor.execute("""
        SELECT 
            t.account_id,
            t.name,
            t.amount,
            t.date,
            t.category,
            t.merchant_name,
            t.pending,
            t.currency
        FROM transactions t
    """)
    
    transactions = old_cursor.fetchall()
    migrated_count = 0
    skipped_count = 0
    
    print(f"\nFound {len(transactions)} transactions to migrate...\n")
    
    for old_account_id, name, amount, date, category, merchant, pending, currency in transactions:
        try:
            # Find new account number
            new_account_number = account_mapping.get(str(old_account_id))
            
            if not new_account_number:
                skipped_count += 1
                continue
            
            # Get phone for this account
            new_cursor.execute("SELECT phone FROM accounts WHERE account_number = ?", 
                             (new_account_number,))
            phone_row = new_cursor.fetchone()
            if not phone_row:
                skipped_count += 1
                continue
            
            phone = phone_row[0]
            
            # Generate transaction ID
            transaction_id = generate_transaction_id()
            
            # Insert transaction
            new_cursor.execute("""
                INSERT INTO transactions (
                    transaction_id, account_number, phone,
                    name, amount, date, category, merchant_name,
                    pending, currency, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
            """, (
                transaction_id, new_account_number, phone,
                name, float(amount) if amount else 0, date, 
                category, merchant, pending or 0, currency or 'USD'
            ))
            
            migrated_count += 1
            
            if migrated_count % 100 == 0:
                print(f"   Migrated {migrated_count} transactions...")
            
        except Exception as e:
            print(f"❌ Error migrating transaction: {e}")
            skipped_count += 1
    
    new_conn.commit()
    
    print(f"\n✅ Migrated {migrated_count} transactions")
    if skipped_count > 0:
        print(f"⚠️  Skipped {skipped_count} transactions (no matching account)")
    
    old_cursor.close()
    new_cursor.close()
    old_conn.close()
    new_conn.close()

def migrate_identity():
    """Migrate user identity data"""
    print("\n" + "="*60)
    print("👤 STEP 4: Migrating User Identity")
    print("="*60)
    
    old_conn = get_connection("BankData")
    new_conn = get_connection("BankData_v2")
    
    old_cursor = old_conn.cursor()
    new_cursor = new_conn.cursor()
    
    old_cursor.execute("""
        SELECT DISTINCT
            phone, full_name, email,
            address_street, address_city, address_state,
            address_zip, address_country
        FROM user_identity
        WHERE phone IS NOT NULL
    """)
    
    identities = old_cursor.fetchall()
    migrated_count = 0
    
    print(f"\nFound {len(identities)} identity records...\n")
    
    for phone, full_name, email, street, city, state, zip_code, country in identities:
        try:
            new_cursor.execute("""
                INSERT INTO user_identity (
                    phone, full_name, email,
                    address_street, address_city, address_state,
                    address_zip, address_country, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
            """, (phone, full_name, email, street, city, state, zip_code, country))
            
            migrated_count += 1
            print(f"✅ Migrated identity for: {full_name} ({phone})")
            
        except Exception as e:
            print(f"⚠️  Identity for {phone} already exists or error: {e}")
    
    new_conn.commit()
    
    print(f"\n✅ Migrated {migrated_count} identity records")
    
    old_cursor.close()
    new_cursor.close()
    old_conn.close()
    new_conn.close()

def migrate_income():
    """Migrate income data"""
    print("\n" + "="*60)
    print("💰 STEP 5: Migrating Income Data")
    print("="*60)
    
    old_conn = get_connection("BankData")
    new_conn = get_connection("BankData_v2")
    
    old_cursor = old_conn.cursor()
    new_cursor = new_conn.cursor()
    
    old_cursor.execute("""
        SELECT 
            ui.phone,
            i.employer_name,
            i.monthly_income,
            i.annual_income,
            i.pay_frequency,
            i.last_payment_date,
            i.last_payment_amount,
            i.confidence
        FROM user_income i
        JOIN items it ON i.item_id = it.item_id
        JOIN user_identity ui ON it.item_id = ui.item_id
        WHERE ui.phone IS NOT NULL
    """)
    
    incomes = old_cursor.fetchall()
    migrated_count = 0
    
    print(f"\nFound {len(incomes)} income records...\n")
    
    for phone, employer, monthly, annual, frequency, last_date, last_amount, confidence in incomes:
        try:
            new_cursor.execute("""
                INSERT INTO user_income (
                    phone, employer_name, monthly_income, annual_income,
                    pay_frequency, last_payment_date, last_payment_amount,
                    confidence, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
            """, (phone, employer, monthly, annual, frequency, last_date, last_amount, confidence))
            
            migrated_count += 1
            print(f"✅ Migrated income for: {phone} - ${monthly}/month")
            
        except Exception as e:
            print(f"❌ Error migrating income: {e}")
    
    new_conn.commit()
    
    print(f"\n✅ Migrated {migrated_count} income records")
    
    old_cursor.close()
    new_cursor.close()
    old_conn.close()
    new_conn.close()

def migrate_liabilities():
    """Migrate liabilities"""
    print("\n" + "="*60)
    print("💳 STEP 6: Migrating Liabilities")
    print("="*60)
    
    old_conn = get_connection("BankData")
    new_conn = get_connection("BankData_v2")
    
    old_cursor = old_conn.cursor()
    new_cursor = new_conn.cursor()
    
    old_cursor.execute("""
        SELECT 
            ui.phone,
            l.liability_type,
            l.balance,
            l.apr,
            l.minimum_payment,
            l.credit_limit,
            l.last_payment_amount,
            l.last_payment_date,
            l.loan_status
        FROM user_liabilities l
        JOIN items it ON l.item_id = it.item_id
        JOIN user_identity ui ON it.item_id = ui.item_id
        WHERE ui.phone IS NOT NULL
    """)
    
    liabilities = old_cursor.fetchall()
    migrated_count = 0
    
    print(f"\nFound {len(liabilities)} liability records...\n")
    
    for phone, lib_type, balance, apr, min_payment, credit_limit, last_amount, last_date, status in liabilities:
        try:
            liability_number = generate_liability_number(lib_type)
            
            new_cursor.execute("""
                INSERT INTO user_liabilities (
                    liability_number, phone, liability_type,
                    balance, apr, minimum_payment, credit_limit,
                    last_payment_amount, last_payment_date, loan_status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
            """, (liability_number, phone, lib_type, balance, apr, min_payment, 
                  credit_limit, last_amount, last_date, status))
            
            migrated_count += 1
            print(f"✅ Migrated {lib_type} for: {phone} - ${balance}")
            
        except Exception as e:
            print(f"❌ Error migrating liability: {e}")
    
    new_conn.commit()
    
    print(f"\n✅ Migrated {migrated_count} liability records")
    
    old_cursor.close()
    new_cursor.close()
    old_conn.close()
    new_conn.close()

def migrate_analytics():
    """Migrate spending analytics"""
    print("\n" + "="*60)
    print("📊 STEP 7: Migrating Analytics")
    print("="*60)
    
    old_conn = get_connection("BankData")
    new_conn = get_connection("BankData_v2")
    
    old_cursor = old_conn.cursor()
    new_cursor = new_conn.cursor()
    
    old_cursor.execute("""
        SELECT 
            ui.phone,
            s.month,
            s.total_income,
            s.total_expenses,
            s.net_cash_flow,
            s.top_category,
            s.top_category_amount,
            s.transaction_count,
            s.avg_transaction_amount
        FROM spending_analytics s
        JOIN items it ON s.item_id = it.item_id
        JOIN user_identity ui ON it.item_id = ui.item_id
        WHERE ui.phone IS NOT NULL
    """)
    
    analytics = old_cursor.fetchall()
    migrated_count = 0
    
    print(f"\nFound {len(analytics)} analytics records...\n")
    
    for phone, month, income, expenses, net, top_cat, top_amt, tx_count, avg_tx in analytics:
        try:
            new_cursor.execute("""
                INSERT INTO spending_analytics (
                    phone, month, total_income, total_expenses,
                    net_cash_flow, top_category, top_category_amount,
                    transaction_count, avg_transaction_amount, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
            """, (phone, month, income, expenses, net, top_cat, top_amt, tx_count, avg_tx))
            
            migrated_count += 1
            
        except Exception as e:
            print(f"❌ Error migrating analytics: {e}")
    
    new_conn.commit()
    
    print(f"✅ Migrated {migrated_count} analytics records")
    
    old_cursor.close()
    new_cursor.close()
    old_conn.close()
    new_conn.close()

def verify_migration():
    """Verify migration was successful"""
    print("\n" + "="*60)
    print("✅ VERIFICATION")
    print("="*60)
    
    new_conn = get_connection("BankData_v2")
    cursor = new_conn.cursor()
    
    tables = [
        "users", "accounts", "transactions", "user_identity",
        "user_income", "user_liabilities", "spending_analytics"
    ]
    
    print("\nRecord counts in BankData_v2:\n")
    
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table:25} {count:>10} records")
    
    cursor.close()
    new_conn.close()
    
    print("\n" + "="*60)

def main():
    print("\n" + "="*70)
    print(" "*20 + "DATA MIGRATION")
    print(" "*15 + "BankData → BankData_v2")
    print("="*70)
    
    try:
        migrate_users()
        migrate_accounts()
        migrate_transactions()
        migrate_identity()
        migrate_income()
        migrate_liabilities()
        migrate_analytics()
        verify_migration()
        
        print("\n" + "="*70)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
        print("="*70)
        print("\n📝 Next Steps:")
        print("   1. Verify data in BankData_v2")
        print("   2. Update .env to use BankData_v2")
        print("   3. Test login with phone + MPIN (0000)")
        print("   4. Test agents with new structure")
        print("\n⚠️  REMINDER: All users have default MPIN: 0000")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()