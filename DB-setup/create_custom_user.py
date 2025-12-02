# insert_custom_user_data.py
"""
Insert a full synthetic USD user profile into BankData_v2.
User: Prajjwal Guhe
Phone: +919970999067
Currency: USD
Created to match the schema in setup_db_v2 (phone-based).
"""

import os
import random
import uuid
import pyodbc
from datetime import datetime, timedelta

# ---------- CONFIG (uses same .env as setup/migration) ----------
from dotenv import load_dotenv
load_dotenv()

SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DATABASE = os.getenv("SQL_DATABASE", "BankData_v2")
SQL_DRIVER = os.getenv("SQL_DRIVER", "ODBC Driver 17 for SQL Server")
SQL_TRUSTED = os.getenv("SQL_TRUSTED_CONNECTION", "No")
SQL_USERNAME = os.getenv("SQL_USERNAME")
SQL_PASSWORD = os.getenv("SQL_PASSWORD")

PHONE = "+919970999067"
NAME = "Prajjwal Guhe"
MPIN = "0000"
CURRENCY = "USD"

def get_connection():
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
            f"UID={SQL_USERNAME};PWD={SQL_PASSWORD};"
        )
    return pyodbc.connect(conn_str)

# ---------- Helpers ----------
def gen_account_number(prefix_digit="1"):
    # 16-digit but ensure leading prefix
    rest = "".join(str(random.randint(0,9)) for _ in range(15))
    return int(prefix_digit + rest[:15])

def gen_transaction_id(counter):
    return counter + random.randint(1, 999)

def rand_date_within(days_back=120):
    return (datetime.utcnow() - timedelta(days=random.randint(0, days_back))).date()

def upsert_user(conn):
    cur = conn.cursor()
    cur.execute("""
        IF NOT EXISTS (SELECT phone FROM users WHERE phone = ?)
        INSERT INTO users (phone, mpin, name, email, created_at, updated_at)
        VALUES (?, ?, ?, ?, SYSUTCDATETIME(), SYSUTCDATETIME())
    """, (PHONE, PHONE, MPIN, NAME, f"{PHONE.replace('+','')}.user@example.com"))
    conn.commit()
    cur.close()

def upsert_identity(conn):
    cur = conn.cursor()
    dob = datetime(1992, 6, 15).date()
    cur.execute("""
        IF NOT EXISTS (SELECT phone FROM user_identity WHERE phone = ?)
        INSERT INTO user_identity (
            phone, full_name, email, date_of_birth,
            address_street, address_city, address_state, address_zip, address_country, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME(), SYSUTCDATETIME())
    """, (PHONE, PHONE, NAME, f"{PHONE.replace('+','')}.user@example.com", dob, "MG Road", "Mumbai", "MH", "400001", "India"))
    conn.commit()
    cur.close()

def insert_accounts(conn):
    cur = conn.cursor()
    accounts = []
    # Checking (prefix 1), Savings (prefix 2), Credit card (prefix 4)
    acct_check = gen_account_number("1")
    acct_save = gen_account_number("2")
    acct_cc = gen_account_number("4")
    accounts.append({"account_number": acct_check, "name": "Primary Checking", "subtype": "checking", "balance_current": 5200.00, "balance_available": 5000.00})
    accounts.append({"account_number": acct_save, "name": "Savings Account", "subtype": "savings", "balance_current": 15400.50, "balance_available": 15400.50})
    accounts.append({"account_number": acct_cc, "name": "Credit Card", "subtype": "credit card", "balance_current": -2400.75, "balance_available": -2400.75})
    for i, a in enumerate(accounts):
        try:
            cur.execute("""
                IF NOT EXISTS (SELECT account_number FROM accounts WHERE account_number = ?)
                INSERT INTO accounts (
                    account_number, phone, name, type, subtype, mask, currency,
                    balance_available, balance_current, is_primary, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', SYSUTCDATETIME(), SYSUTCDATETIME())
            """, (
                a["account_number"], a["account_number"], PHONE, a["name"],
                'depository' if 'credit' not in a['subtype'] else 'credit', a['subtype'],
                str(a["account_number"])[-4:], CURRENCY,
                float(a["balance_available"]), float(a["balance_current"]),
                1 if i == 0 else 0
            ))
        except Exception as e:
            print("Account insert error:", e)
    conn.commit()
    cur.close()
    return [acct_check, acct_save, acct_cc]

def insert_income(conn, primary_account):
    cur = conn.cursor()
    income_id = str(uuid.uuid4())
    monthly = 4800.00  # USD value as requested
    annual = monthly * 12
    cur.execute("""
        INSERT INTO user_income (
            income_id, phone, account_number, employer_name, monthly_income, annual_income,
            pay_frequency, last_payment_date, last_payment_amount, confidence, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
    """, (income_id, PHONE, primary_account, "Acme Solutions Pvt Ltd", monthly, annual, "monthly", datetime.utcnow().date(), monthly, 0.98))
    conn.commit()
    cur.close()

def insert_liabilities(conn, cc_account):
    cur = conn.cursor()
    # credit card liability
    liab_num_cc = gen_account_number("4")
    cur.execute("""
        INSERT INTO user_liabilities (
            liability_number, phone, liability_type, balance, apr, minimum_payment,
            credit_limit, last_payment_amount, last_payment_date, origination_date,
            maturity_date, loan_term, loan_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
    """, (liab_num_cc, PHONE, "Credit Card", 2400.75, 18.99, 75.00, 10000.00, 120.00, (datetime.utcnow() - timedelta(days=25)).date(), (datetime.utcnow() - timedelta(days=365)).date(), None, None, "active"))
    # small personal loan
    liab_num_loan = gen_account_number("6")
    cur.execute("""
        INSERT INTO user_liabilities (
            liability_number, phone, liability_type, balance, apr, minimum_payment,
            credit_limit, last_payment_amount, last_payment_date, origination_date,
            maturity_date, loan_term, loan_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
    """, (liab_num_loan, PHONE, "Personal Loan", 8200.00, 10.50, 220.00, None, 220.00, (datetime.utcnow() - timedelta(days=30)).date(), (datetime.utcnow() - timedelta(days=720)).date(), (datetime.utcnow() + timedelta(days=365*4)).date(), 60, "active"))
    conn.commit()
    cur.close()

def insert_transactions(conn, account_numbers, tx_count=120):
    cur = conn.cursor()
    # Start counter for transaction_id
    base_counter = int(datetime.utcnow().strftime("%Y%m%d")) * 100000
    categories = ["groceries", "salary", "rent", "utilities", "subscriptions", "transport", "dining", "shopping", "travel", "health"]
    merchants = ["Walmart", "Amazon", "Uber", "Spotify", "Shell", "Starbucks", "Zomato", "BigMart", "AirlineCo", "PharmaPlus"]
    inserted = 0
    for i in range(tx_count):
        account = random.choices(account_numbers, weights=[0.6, 0.2, 0.2])[0]  # more on checking
        is_credit = random.random() < 0.08  # salary / refunds
        amt = round(random.uniform(3.5, 250.0), 2)
        if is_credit and i % 15 != 0:
            # occasional higher credits
            amt = round(random.uniform(20, 3000), 2)
        # make periodic salary credits
        if i % 30 == 0:
            category = "salary"
            amt = 4800.00
            is_credit = True
        else:
            category = random.choice(categories)
        sign_amt = -amt if not is_credit else -amt if category == "salary" else abs(amt) * -1
        # Note: in your DB migration transactions used positive for expenses; keep currency positive for expense
        amount_to_store = float(amt) if category != "salary" else float(-amt)  # follow earlier code where expenses positive
        tx_date = rand_date_within(120)
        tx_id = gen_transaction_id(base_counter + i)
        merchant = random.choice(merchants)
        pending = 0 if random.random() > 0.05 else 1
        try:
            cur.execute("""
                INSERT INTO transactions (
                    transaction_id, account_number, phone, name, amount, date,
                    category, merchant_name, pending, currency, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
            """, (tx_id, account, PHONE, f"{merchant} purchase", amount_to_store, tx_date, category, merchant, pending, CURRENCY))
            inserted += 1
            if inserted % 200 == 0:
                conn.commit()
        except Exception as e:
            print("Transaction insert error:", e)
    conn.commit()
    cur.close()

def insert_spending_analytics(conn, account_numbers):
    cur = conn.cursor()
    today = datetime.utcnow().date()
    for m in range(3):
        month_date = (today - timedelta(days=30*m)).replace(day=1)
        # fake monthly numbers
        total_income = 4800.00
        total_expenses = round(random.uniform(2000, 4500), 2)
        net = total_income - total_expenses
        top_category = random.choice(["groceries", "rent", "dining", "shopping"])
        top_amt = round(total_expenses * random.uniform(0.15, 0.45), 2)
        tx_count = random.randint(30, 60)
        avg_tx = round(total_expenses / max(1, tx_count), 2)
        cur.execute("""
            INSERT INTO spending_analytics (
                analytics_id, phone, account_number, month, total_income, total_expenses,
                net_cash_flow, top_category, top_category_amount, transaction_count, avg_transaction_amount, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
        """, (str(uuid.uuid4()), PHONE, account_numbers[0], month_date, total_income, total_expenses, net, top_category, top_amt, tx_count, avg_tx))
    conn.commit()
    cur.close()

def main():
    conn = get_connection()
    try:
        upsert_user(conn)
        upsert_identity(conn)
        account_numbers = insert_accounts(conn)
        insert_income(conn, account_numbers[0])
        insert_liabilities(conn, account_numbers[2])
        insert_transactions(conn, account_numbers, tx_count=120)
        insert_spending_analytics(conn, account_numbers)
        print("✅ Inserted synthetic user data for", PHONE)
    except Exception as e:
        print("❌ Error while inserting data:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
