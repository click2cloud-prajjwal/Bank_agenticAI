# backend/db.py
import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

SQL_SERVER = os.getenv("SQL_SERVER")          # e.g. "10.0.0.5,1433"
SQL_DATABASE = os.getenv("SQL_DATABASE")      # e.g. "BankData"
SQL_USERNAME = os.getenv("SQL_USERNAME")
SQL_PASSWORD = os.getenv("SQL_PASSWORD")

SQL_DRIVER = "ODBC Driver 17 for SQL Server"   # keep fixed

def build_connection_string():
    return (
        f"DRIVER={{{SQL_DRIVER}}};"
        f"SERVER={SQL_SERVER};"              # IP,Port works here
        f"DATABASE={SQL_DATABASE};"
        f"UID={SQL_USERNAME};"
        f"PWD={SQL_PASSWORD};"
    )

def get_connection():
    try:
        return pyodbc.connect(build_connection_string(), autocommit=False)
    except Exception as e:
        print("DB connection error:", e)
        raise
