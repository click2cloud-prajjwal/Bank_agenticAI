# backend/setup_db.py

import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()

SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DATABASE = os.getenv("SQL_DATABASE", "BankData")
SQL_DRIVER = os.getenv("SQL_DRIVER", "ODBC Driver 17 for SQL Server")
SQL_TRUSTED = os.getenv("SQL_TRUSTED_CONNECTION", "No")
SQL_USERNAME = os.getenv("SQL_USERNAME")
SQL_PASSWORD = os.getenv("SQL_PASSWORD")

def get_connection_to_finance_db():
    """Connect directly to BankData database (already created)."""
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


def run():
    print("\n🚀 Setting up BankData tables and encryption inside existing database...\n")

    # Connect to BankData DB
    conn = get_connection_to_finance_db()
    cursor = conn.cursor()

    # ---------------------------------------------
    # 1) MASTER KEY, CERTIFICATE, SYMMETRIC KEY
    # ---------------------------------------------
    print("🔐 Creating encryption keys...")

    try:
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.symmetric_keys WHERE name='##MS_DatabaseMasterKey##')
        BEGIN
            CREATE MASTER KEY ENCRYPTION BY PASSWORD = 'Very$trongPassw0rd!';
        END
        """)
        conn.commit()
    except Exception as e:
        print("Master key already exists or error:", e)

    try:
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.certificates WHERE name='PlaidCert')
        BEGIN
            CREATE CERTIFICATE PlaidCert WITH SUBJECT='Plaid Token Certificate';
        END
        """)
        conn.commit()
    except Exception as e:
        print("Certificate already exists or error:", e)

    try:
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.symmetric_keys WHERE name='PlaidKey')
        BEGIN
            CREATE SYMMETRIC KEY PlaidKey
            WITH ALGORITHM = AES_256
            ENCRYPTION BY CERTIFICATE PlaidCert;
        END
        """)
        conn.commit()
    except Exception as e:
        print("Symmetric key already exists or error:", e)

    print("✅ Encryption keys ready.\n")


    # ---------------------------------------------
    # 2) CREATE TABLES
    # ---------------------------------------------
    print("📦 Creating tables...")

    TABLES = [

        # users
        """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE name='users')
        BEGIN
            CREATE TABLE users (
                user_id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
                name NVARCHAR(255),
                email NVARCHAR(255),
                created_at DATETIME2 DEFAULT SYSUTCDATETIME()
            );
        END
        """,

        # items
        """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE name='items')
        BEGIN
            CREATE TABLE items (
                item_id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
                user_id UNIQUEIDENTIFIER,
                plaid_item_id NVARCHAR(255) NOT NULL,
                access_token VARBINARY(MAX),
                institution_id NVARCHAR(255),
                transactions_cursor NVARCHAR(500),
                created_at DATETIME2 DEFAULT SYSUTCDATETIME()
            );
        END
        """,

        # accounts
        """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE name='accounts')
        BEGIN
            CREATE TABLE accounts (
                account_id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
                item_id UNIQUEIDENTIFIER NULL,
                plaid_account_id NVARCHAR(255) NOT NULL,
                name NVARCHAR(255),
                type NVARCHAR(60),
                subtype NVARCHAR(60),
                mask NVARCHAR(10),
                currency NVARCHAR(10),
                balance_available DECIMAL(18,2),
                balance_current DECIMAL(18,2),
                created_at DATETIME2 DEFAULT SYSUTCDATETIME()
            );
        END
        """,

        # transactions
        """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE name='transactions')
        BEGIN
            CREATE TABLE transactions (
                transaction_id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
                account_id UNIQUEIDENTIFIER NULL,
                plaid_transaction_id NVARCHAR(255) NOT NULL,
                name NVARCHAR(255),
                amount DECIMAL(18,2),
                date DATE,
                category NVARCHAR(500),
                merchant_name NVARCHAR(255),
                pending BIT,
                currency NVARCHAR(10),
                created_at DATETIME2 DEFAULT SYSUTCDATETIME()
            );
        END
        """,

        # user_identity (from Plaid Identity API)
        """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE name='user_identity')
        BEGIN
            CREATE TABLE user_identity (
                identity_id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
                item_id UNIQUEIDENTIFIER NULL,
                plaid_account_id NVARCHAR(255) NOT NULL,
                full_name NVARCHAR(255),
                email NVARCHAR(255),
                phone NVARCHAR(50),
                address_street NVARCHAR(500),
                address_city NVARCHAR(100),
                address_state NVARCHAR(50),
                address_zip NVARCHAR(20),
                address_country NVARCHAR(50),
                created_at DATETIME2 DEFAULT SYSUTCDATETIME()
            );
        END
        """,

        # user_income (from Plaid Income API)
        """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE name='user_income')
        BEGIN
            CREATE TABLE user_income (
                income_id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
                item_id UNIQUEIDENTIFIER NULL,
                plaid_account_id NVARCHAR(255) NOT NULL,
                employer_name NVARCHAR(255),
                monthly_income DECIMAL(18,2),
                annual_income DECIMAL(18,2),
                pay_frequency NVARCHAR(50),
                last_payment_date DATE,
                last_payment_amount DECIMAL(18,2),
                confidence DECIMAL(5,2),
                created_at DATETIME2 DEFAULT SYSUTCDATETIME()
            );
        END
        """,

        # user_liabilities (from Plaid Liabilities API)
        """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE name='user_liabilities')
        BEGIN
            CREATE TABLE user_liabilities (
                liability_id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
                item_id UNIQUEIDENTIFIER NULL,
                plaid_account_id NVARCHAR(255) NOT NULL,
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
                created_at DATETIME2 DEFAULT SYSUTCDATETIME()
            );
        END
        """,

        # spending_analytics (calculated from transactions)
        """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE name='spending_analytics')
        BEGIN
            CREATE TABLE spending_analytics (
                analytics_id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
                item_id UNIQUEIDENTIFIER NULL,
                account_id UNIQUEIDENTIFIER NULL,
                month DATE NOT NULL,
                total_income DECIMAL(18,2),
                total_expenses DECIMAL(18,2),
                net_cash_flow DECIMAL(18,2),
                top_category NVARCHAR(100),
                top_category_amount DECIMAL(18,2),
                transaction_count INT,
                avg_transaction_amount DECIMAL(18,2),
                created_at DATETIME2 DEFAULT SYSUTCDATETIME()
            );
        END
        """,

        # agent_insights
        """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE name='agent_insights')
        BEGIN
            CREATE TABLE agent_insights (
                insight_id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
                user_id UNIQUEIDENTIFIER,
                item_id UNIQUEIDENTIFIER NULL,
                insight_type NVARCHAR(100),
                insight_text NVARCHAR(MAX),
                confidence_score DECIMAL(5,2),
                created_at DATETIME2 DEFAULT SYSUTCDATETIME()
            );
        END
        """
    ]

    for sql in TABLES:
        cursor.execute(sql)
        conn.commit()

    print("✅ Tables created.\n")


    # ---------------------------------------------
    # 3) CREATE INDEXES
    # ---------------------------------------------
    print("⚡ Creating indexes...")

    INDEXES = [
        "IF NOT EXISTS(SELECT name FROM sys.indexes WHERE name='idx_item_plaid') CREATE INDEX idx_item_plaid ON items(plaid_item_id);",
        "IF NOT EXISTS(SELECT name FROM sys.indexes WHERE name='idx_account_plaid') CREATE INDEX idx_account_plaid ON accounts(plaid_account_id);",
        "IF NOT EXISTS(SELECT name FROM sys.indexes WHERE name='idx_tx_plaid') CREATE INDEX idx_tx_plaid ON transactions(plaid_transaction_id);",
        "IF NOT EXISTS(SELECT name FROM sys.indexes WHERE name='idx_tx_account') CREATE INDEX idx_tx_account ON transactions(account_id);",
        "IF NOT EXISTS(SELECT name FROM sys.indexes WHERE name='idx_account_item') CREATE INDEX idx_account_item ON accounts(item_id);",
        "IF NOT EXISTS(SELECT name FROM sys.indexes WHERE name='idx_identity_account') CREATE INDEX idx_identity_account ON user_identity(plaid_account_id);",
        "IF NOT EXISTS(SELECT name FROM sys.indexes WHERE name='idx_income_account') CREATE INDEX idx_income_account ON user_income(plaid_account_id);",
        "IF NOT EXISTS(SELECT name FROM sys.indexes WHERE name='idx_liabilities_account') CREATE INDEX idx_liabilities_account ON user_liabilities(plaid_account_id);",
    ]

    for idx in INDEXES:
        cursor.execute(idx)
        conn.commit()

    print("✅ Indexes created.\n")

    conn.close()
    print("DONE! BankData database setup complete.\n")


if __name__ == "__main__":
    run()