import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DATABASE = os.getenv("SQL_DATABASE")
SQL_DRIVER = os.getenv("SQL_DRIVER")
SQL_TRUSTED = os.getenv("SQL_TRUSTED_CONNECTION")

print("------------------------------------------------")
print(" DB CONNECTION CHECK")
print("------------------------------------------------")
print("SERVER:", SQL_SERVER)
print("DATABASE:", SQL_DATABASE)
print("DRIVER:", SQL_DRIVER)
print("TRUSTED:", SQL_TRUSTED)
print("------------------------------------------------")

# Build connection string
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
        f"UID={os.getenv('SQL_USERNAME')};PWD={os.getenv('SQL_PASSWORD')};"
    )

try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    print("✔ Connected successfully to database:", SQL_DATABASE)
except Exception as e:
    print("❌ FAILED to connect:", e)
    raise SystemExit()


# ----------------------------------------------------
# 1) Check column structure of items table
# ----------------------------------------------------
print("\n--- Checking items table structure ---")
try:
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'items'
    """)
    rows = cursor.fetchall()

    if not rows:
        print("❌ items table does not exist.")
    else:
        for r in rows:
            print(f"{r.COLUMN_NAME}: {r.DATA_TYPE} ({r.CHARACTER_MAXIMUM_LENGTH})")

except Exception as e:
    print("❌ Error reading table structure:", e)


# ----------------------------------------------------
# 2) Try decrypting stored access tokens
# ----------------------------------------------------
print("\n--- Checking decryption of access_token ---")

try:
    cursor.execute("OPEN SYMMETRIC KEY PlaidKey DECRYPTION BY CERTIFICATE PlaidCert;")

    cursor.execute("""
        SELECT 
            TOP 5 plaid_item_id,
            CONVERT(VARCHAR(MAX), DecryptByKey(access_token)) AS decrypted_token
        FROM items
    """)

    rows = cursor.fetchall()

    cursor.execute("CLOSE SYMMETRIC KEY PlaidKey;")

    if not rows:
        print("No rows in items table.")
    else:
        for r in rows:
            print("item_id:", r.plaid_item_id, "| decrypted_token:", r.decrypted_token)

except Exception as e:
    print("❌ Decryption error:", e)

print("\n------------------------------------------------")
print("CHECK COMPLETED")
print("------------------------------------------------")
