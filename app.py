# app.py
import os
import traceback
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
from agents.orchestrator import Orchestrator

load_dotenv()

from plaid_service import get_plaid_client
from db import get_connection

app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

plaid_client = get_plaid_client()
orchestrator = Orchestrator()

@app.route("/")
def serve_home():
    return send_from_directory("static", "index.html")


# ----------------------------
# 1) create_link_token
# ----------------------------
@app.route("/create_link_token", methods=["POST"])
def create_link_token():
    try:
        req_json = request.get_json() or {}
        client_user_id = req_json.get("client_user_id", "dev-user-1")

        req = {
            "client_name": "FinanceAI",
            "language": "en",
            "country_codes": ["US"],
            "user": {"client_user_id": client_user_id},
            "products": [
                "transactions",  # ✅ Available in Sandbox
                "auth",          # ✅ Available in Sandbox
                "identity"       # ✅ Available in Sandbox (usually)
            ],
        }

        res = plaid_client.link_token_create(req)
        return jsonify(res.to_dict())
    except Exception as e:
        tb = traceback.format_exc()
        return jsonify({"error": "create_link_token_failed", "exception": str(e), "trace": tb}), 500


# ----------------------------
# 2) exchange_public_token
# ----------------------------
@app.route("/exchange_public_token", methods=["POST"])
def exchange_public_token():
    """
    Exchange a public_token returned by Plaid Link for an access_token,
    then store the access_token (encrypted) in the items table.
    """
    conn = None
    try:
        data = request.get_json() or {}
        public_token = data.get("public_token")
        if not public_token:
            return jsonify({"error": "public_token_required"}), 400

        exchange_request = {"public_token": public_token}
        exchange_response = plaid_client.item_public_token_exchange(exchange_request)

        access_token = exchange_response["access_token"]
        item_id = exchange_response["item_id"]

        print("✅ Access token received:", access_token)

        # Save encrypted access_token into DB
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("OPEN SYMMETRIC KEY PlaidKey DECRYPTION BY CERTIFICATE PlaidCert;")

        insert_sql = """
            INSERT INTO items (user_id, plaid_item_id, access_token, institution_id, created_at)
            VALUES (NEWID(), ?, EncryptByKey(Key_GUID('PlaidKey'), ?), NULL, SYSUTCDATETIME());
        """

        cursor.execute(insert_sql, (item_id, access_token))
        cursor.execute("CLOSE SYMMETRIC KEY PlaidKey;")

        conn.commit()
        cursor.close()

        return jsonify({"item_id": item_id})
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        tb = traceback.format_exc()
        return jsonify({"error": "exchange_failed", "exception": str(e), "trace": tb}), 500
    finally:
        if conn:
            conn.close()


# ----------------------------
# Helper: Get Access Token
# ----------------------------
def get_access_token(item_id):
    """Helper function to decrypt and return access token"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("OPEN SYMMETRIC KEY PlaidKey DECRYPTION BY CERTIFICATE PlaidCert;")
    cursor.execute("""
        SELECT CONVERT(NVARCHAR(MAX), DecryptByKey(access_token))
        FROM items WHERE plaid_item_id = ?;
    """, (item_id,))
    row = cursor.fetchone()
    cursor.execute("CLOSE SYMMETRIC KEY PlaidKey;")
    conn.close()
    
    if not row or not row[0]:
        return None
    return row[0]


# ----------------------------
# 3) fetch_all_data - Complete Data Pipeline
# ----------------------------
@app.route("/fetch_all_data", methods=["POST"])
def fetch_all_data():
    """
    Fetch ALL available data from Plaid Sandbox:
    - Accounts & Balances
    - Transactions
    - Identity
    - Derived Income (from deposits)
    - Derived Liabilities (from credit cards)
    Body: { "item_id": "..." }
    """
    try:
        data = request.get_json() or {}
        item_id = data.get("item_id")
        if not item_id:
            return jsonify({"error": "item_id_required"}), 400

        results = {}
        
        print("\n" + "="*60)
        print("FETCHING ALL DATA FROM PLAID SANDBOX")
        print("="*60)
        
        # 1. Accounts & Transactions
        print("\n📊 Fetching Accounts & Transactions...")
        results['accounts'] = fetch_accounts_and_transactions(item_id)
        
        # 2. Identity
        print("\n👤 Fetching Identity...")
        results['identity'] = fetch_identity_data(item_id)
        
        # 3. Derive Income (from transaction deposits)
        print("\n💰 Deriving Income from Transactions...")
        results['income'] = derive_income_from_transactions(item_id)
        
        # 4. Derive Liabilities (from credit card balances)
        print("\n💳 Deriving Liabilities from Accounts...")
        results['liabilities'] = derive_liabilities_from_accounts(item_id)
        
        # 5. Calculate Analytics
        print("\n📈 Calculating Spending Analytics...")
        results['analytics'] = calculate_spending_analytics(item_id)
        
        print("\n" + "="*60)
        print("✅ ALL DATA FETCHED SUCCESSFULLY")
        print("="*60)
        
        return jsonify({
            "message": "all_data_fetched_successfully",
            "summary": results
        })
        
    except Exception as e:
        tb = traceback.format_exc()
        return jsonify({"error": "fetch_all_failed", "exception": str(e), "trace": tb}), 500


# ----------------------------
# Fetch Accounts & Transactions
# ----------------------------
def fetch_accounts_and_transactions(item_id):
    """Fetch accounts and transactions"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        access_token = get_access_token(item_id)
        if not access_token:
            return {"error": "access_token_not_found"}
        
        # Fetch Accounts
        accounts_res = plaid_client.accounts_get({"access_token": access_token})
        accounts = accounts_res.to_dict().get("accounts", [])
        
        # Upsert accounts
        for acc in accounts:
            upsert_sql = """
                IF EXISTS (SELECT 1 FROM accounts WHERE plaid_account_id = ?)
                BEGIN
                    UPDATE accounts
                    SET name = ?, type = ?, subtype = ?, mask = ?, currency = ?, 
                        balance_available = ?, balance_current = ?, created_at = SYSUTCDATETIME()
                    WHERE plaid_account_id = ?
                END
                ELSE
                BEGIN
                    INSERT INTO accounts (account_id, item_id, plaid_account_id, name, type, subtype, mask, currency, balance_available, balance_current, created_at)
                    VALUES (NEWID(), (SELECT item_id FROM items WHERE plaid_item_id = ?), ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
                END
            """
            cursor.execute(upsert_sql, (
                acc["account_id"],
                acc.get("name"), acc.get("type"), acc.get("subtype"), acc.get("mask"),
                acc["balances"].get("iso_currency_code"), acc["balances"].get("available"),
                acc["balances"].get("current"), acc["account_id"],
                item_id, acc["account_id"], acc.get("name"), acc.get("type"), 
                acc.get("subtype"), acc.get("mask"), acc["balances"].get("iso_currency_code"),
                acc["balances"].get("available"), acc["balances"].get("current")
            ))
        
        # Fetch Transactions via Sync
        cursor.execute("SELECT transactions_cursor FROM items WHERE plaid_item_id = ?;", (item_id,))
        cursor_row = cursor.fetchone()
        stored_cursor = cursor_row[0] if cursor_row and cursor_row[0] else None
        
        cursor_value = stored_cursor
        has_more = True
        all_transactions = []
        
        while has_more:
            sync_req = {"access_token": access_token}
            if cursor_value:
                sync_req["cursor"] = cursor_value
            
            sync_res = plaid_client.transactions_sync(sync_req)
            sync_data = sync_res.to_dict()
            
            added = sync_data.get("added", [])
            all_transactions.extend(added)
            
            has_more = sync_data.get("has_more", False)
            cursor_value = sync_data.get("next_cursor")
        
        # Save cursor
        cursor.execute("UPDATE items SET transactions_cursor = ? WHERE plaid_item_id = ?;", (cursor_value, item_id))
        
        # Insert transactions
        for tx in all_transactions:
            category = ",".join(tx.get("category") or [])
            insert_tx_sql = """
                IF NOT EXISTS (SELECT 1 FROM transactions WHERE plaid_transaction_id = ?)
                BEGIN
                    INSERT INTO transactions (transaction_id, account_id, plaid_transaction_id, name, amount, date, category, merchant_name, pending, currency, created_at)
                    VALUES (NEWID(), (SELECT account_id FROM accounts WHERE plaid_account_id = ?), ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
                END
            """
            cursor.execute(insert_tx_sql, (
                tx["transaction_id"], tx["account_id"], tx["transaction_id"],
                tx.get("name"), tx.get("amount"), tx.get("date"), category,
                tx.get("merchant_name"), 1 if tx.get("pending") else 0, tx.get("iso_currency_code")
            ))
        
        conn.commit()
        print(f"✅ Accounts: {len(accounts)}, Transactions: {len(all_transactions)}")
        return {"accounts_count": len(accounts), "transactions_count": len(all_transactions)}
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


# ----------------------------
# Fetch Identity Data
# ----------------------------
def fetch_identity_data(item_id):
    """Fetch identity information from Plaid"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        access_token = get_access_token(item_id)
        if not access_token:
            return {"error": "access_token_not_found"}
        
        try:
            identity_res = plaid_client.identity_get({"access_token": access_token})
            identity_data = identity_res.to_dict()
        except Exception as e:
            print(f"⚠️  Identity API not available: {e}")
            return {"identity_count": 0, "note": "Identity API not available in Sandbox"}
        
        accounts = identity_data.get("accounts", [])
        
        identity_count = 0
        for account in accounts:
            owners = account.get("owners", [])
            for owner in owners:
                names = owner.get("names", [])
                emails = owner.get("emails", [])
                phones = owner.get("phone_numbers", [])
                addresses = owner.get("addresses", [])
                
                full_name = names[0] if names else None
                email = emails[0].get("data") if emails else None
                phone = phones[0].get("data") if phones else None
                
                address_data = addresses[0].get("data") if addresses else {}
                
                cursor.execute("""
                    IF NOT EXISTS (SELECT 1 FROM user_identity WHERE plaid_account_id = ?)
                    BEGIN
                        INSERT INTO user_identity (
                            identity_id, item_id, plaid_account_id, full_name, email, phone,
                            address_street, address_city, address_state, address_zip, address_country, created_at
                        )
                        VALUES (
                            NEWID(), (SELECT item_id FROM items WHERE plaid_item_id = ?), ?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME()
                        )
                    END
                """, (
                    account["account_id"], item_id, account["account_id"],
                    full_name, email, phone,
                    address_data.get("street"), address_data.get("city"),
                    address_data.get("region"), address_data.get("postal_code"),
                    address_data.get("country")
                ))
                identity_count += 1
        
        conn.commit()
        print(f"✅ Identity records: {identity_count}")
        return {"identity_count": identity_count}
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


# ----------------------------
# Derive Income from Transactions
# ----------------------------
def derive_income_from_transactions(item_id):
    """Calculate income from transaction deposits (negative amounts = income in Plaid)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get item UUID
        cursor.execute("SELECT item_id FROM items WHERE plaid_item_id = ?", (item_id,))
        row = cursor.fetchone()
        if not row:
            return {"error": "item_not_found"}
        item_uuid = row[0]
        
        # Calculate income from deposits (last 3 months)
        cursor.execute("""
            SELECT 
                a.plaid_account_id,
                COUNT(CASE WHEN t.amount < 0 THEN 1 END) as deposit_count,
                SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END) as total_deposits,
                AVG(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END) as avg_deposit
            FROM transactions t
            JOIN accounts a ON t.account_id = a.account_id
            WHERE a.item_id = ?
            AND t.date >= DATEADD(MONTH, -3, GETDATE())
            AND t.amount < 0
            GROUP BY a.plaid_account_id
            HAVING COUNT(CASE WHEN t.amount < 0 THEN 1 END) > 0
        """, (item_uuid,))
        
        income_rows = cursor.fetchall()
        
        for row in income_rows:
            account_id, deposit_count, total_deposits, avg_deposit = row
            
            # Estimate monthly income
            monthly_income = total_deposits / 3  # Average over 3 months
            annual_income = monthly_income * 12
            
            # Try to identify employer from largest deposits
            cursor.execute("""
                SELECT TOP 1 name
                FROM transactions t
                JOIN accounts a ON t.account_id = a.account_id
                WHERE a.plaid_account_id = ?
                AND t.amount < 0
                AND t.name IS NOT NULL
                ORDER BY ABS(t.amount) DESC
            """, (account_id,))
            
            employer_row = cursor.fetchone()
            employer_name = employer_row[0] if employer_row else "Estimated from deposits"
            
            # Determine pay frequency
            if deposit_count >= 6:  # ~2 per month
                pay_frequency = "BIWEEKLY"
            elif deposit_count >= 3:
                pay_frequency = "MONTHLY"
            else:
                pay_frequency = "IRREGULAR"
            
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM user_income WHERE item_id = ? AND plaid_account_id = ?)
                BEGIN
                    INSERT INTO user_income (
                        income_id, item_id, plaid_account_id, employer_name,
                        monthly_income, annual_income, pay_frequency,
                        confidence, created_at
                    )
                    VALUES (NEWID(), ?, ?, ?, ?, ?, ?, 75.0, SYSUTCDATETIME())
                END
            """, (
                item_uuid, account_id,
                item_uuid, account_id, employer_name,
                monthly_income, annual_income, pay_frequency
            ))
        
        conn.commit()
        print(f"✅ Derived income for {len(income_rows)} accounts")
        return {"income_count": len(income_rows), "note": "Estimated from transaction deposits"}
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


# ----------------------------
# Derive Liabilities from Accounts
# ----------------------------
def derive_liabilities_from_accounts(item_id):
    """Calculate liabilities from credit card account balances"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get item UUID
        cursor.execute("SELECT item_id FROM items WHERE plaid_item_id = ?", (item_id,))
        row = cursor.fetchone()
        if not row:
            return {"error": "item_not_found"}
        item_uuid = row[0]
        
        # Get credit card accounts
        cursor.execute("""
            SELECT 
                plaid_account_id,
                name,
                balance_current,
                balance_available
            FROM accounts
            WHERE item_id = ?
            AND type = 'credit'
        """, (item_uuid,))
        
        credit_accounts = cursor.fetchall()
        
        for account in credit_accounts:
            account_id, name, balance, available = account
            
            # For credit cards, balance is typically negative (what you owe)
            balance = abs(balance) if balance else 0
            
            # Estimate credit limit
            if available:
                credit_limit = balance + abs(available)
            else:
                credit_limit = balance * 2 if balance > 0 else 1000  # Default estimate
            
            # Calculate minimum payment (2.5% of balance or $25, whichever is higher)
            minimum_payment = max(balance * 0.025, 25) if balance > 0 else 0
            
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM user_liabilities WHERE item_id = ? AND plaid_account_id = ?)
                BEGIN
                    INSERT INTO user_liabilities (
                        liability_id, item_id, plaid_account_id, liability_type,
                        balance, minimum_payment, credit_limit, apr, created_at
                    )
                    VALUES (NEWID(), ?, ?, 'Credit Card', ?, ?, ?, 18.99, SYSUTCDATETIME())
                END
            """, (
                item_uuid, account_id,
                item_uuid, account_id,
                balance, minimum_payment, credit_limit
            ))
        
        conn.commit()
        print(f"✅ Found {len(credit_accounts)} credit card liabilities")
        return {"liabilities_count": len(credit_accounts), "note": "Derived from credit card balances"}
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


# ----------------------------
# Calculate Spending Analytics
# ----------------------------
def calculate_spending_analytics(item_id):
    """Calculate spending patterns from transactions"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get item UUID
        cursor.execute("SELECT item_id FROM items WHERE plaid_item_id = ?", (item_id,))
        row = cursor.fetchone()
        if not row:
            return {"error": "item_not_found"}
        item_uuid = row[0]
        
        # Calculate monthly analytics
        cursor.execute("""
            SELECT 
                DATEFROMPARTS(YEAR(t.date), MONTH(t.date), 1) AS month,
                a.account_id,
                SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END) AS total_income,
                SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END) AS total_expenses,
                COUNT(*) AS transaction_count,
                AVG(ABS(t.amount)) AS avg_transaction
            FROM transactions t
            JOIN accounts a ON t.account_id = a.account_id
            WHERE a.item_id = ?
            GROUP BY YEAR(t.date), MONTH(t.date), a.account_id
        """, (item_uuid,))
        
        analytics = cursor.fetchall()
        
        for row in analytics:
            month, account_id, total_income, total_expenses, tx_count, avg_tx = row
            net_cash_flow = (total_income or 0) - (total_expenses or 0)
            
            # Get top spending category for this month
            cursor.execute("""
                SELECT TOP 1 category, SUM(amount) as total
                FROM transactions
                WHERE account_id = ? 
                AND YEAR(date) = YEAR(?) 
                AND MONTH(date) = MONTH(?)
                AND amount > 0
                AND category IS NOT NULL
                AND category != ''
                GROUP BY category
                ORDER BY SUM(amount) DESC
            """, (account_id, month, month))
            
            top_cat_row = cursor.fetchone()
            top_category = top_cat_row[0] if top_cat_row else None
            top_category_amount = top_cat_row[1] if top_cat_row else 0
            
            # Insert analytics
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM spending_analytics WHERE item_id = ? AND account_id = ? AND month = ?)
                BEGIN
                    INSERT INTO spending_analytics (
                        analytics_id, item_id, account_id, month,
                        total_income, total_expenses, net_cash_flow,
                        top_category, top_category_amount,
                        transaction_count, avg_transaction_amount, created_at
                    )
                    VALUES (NEWID(), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
                END
            """, (
                item_uuid, account_id, month,
                item_uuid, account_id, month,
                total_income, total_expenses, net_cash_flow,
                top_category, top_category_amount,
                tx_count, avg_tx
            ))
        
        conn.commit()
        print(f"✅ Analytics calculated for {len(analytics)} months")
        return {"analytics_count": len(analytics)}
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


# ----------------------------
# Get User Context for AI
# ----------------------------
@app.route("/get_user_context", methods=["POST"])
def get_user_context():
    """
    Get complete financial context for a user for AI analysis
    Body: { "item_id": "..." }
    """
    try:
        data = request.get_json() or {}
        item_id = data.get("item_id")
        if not item_id:
            return jsonify({"error": "item_id_required"}), 400
        
        conn = get_connection()
        cursor = conn.cursor()
        
        context = {}
        
        # Get item UUID
        cursor.execute("SELECT item_id FROM items WHERE plaid_item_id = ?", (item_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "item_not_found"}), 404
        item_uuid = row[0]
        
        # 1. Identity
        cursor.execute("""
            SELECT full_name, email, phone, address_city, address_state
            FROM user_identity WHERE item_id = ?
        """, (item_uuid,))
        identity = cursor.fetchone()
        if identity:
            context['identity'] = {
                'name': identity[0],
                'email': identity[1],
                'phone': identity[2],
                'city': identity[3],
                'state': identity[4]
            }
        
        # 2. Income
        cursor.execute("""
            SELECT employer_name, monthly_income, annual_income, pay_frequency
            FROM user_income WHERE item_id = ?
        """, (item_uuid,))
        income_rows = cursor.fetchall()
        context['income'] = [{
            'employer': row[0],
            'monthly': float(row[1]) if row[1] else 0,
            'annual': float(row[2]) if row[2] else 0,
            'frequency': row[3]
        } for row in income_rows]
        
        # 3. Accounts & Balances
        cursor.execute("""
            SELECT name, type, subtype, balance_current, balance_available
            FROM accounts WHERE item_id = ?
        """, (item_uuid,))
        account_rows = cursor.fetchall()
        context['accounts'] = [{
            'name': row[0],
            'type': row[1],
            'subtype': row[2],
            'balance': float(row[3]) if row[3] else 0,
            'available': float(row[4]) if row[4] else 0
        } for row in account_rows]
        
        # 4. Liabilities
        cursor.execute("""
            SELECT liability_type, balance, apr, minimum_payment, credit_limit
            FROM user_liabilities WHERE item_id = ?
        """, (item_uuid,))
        liability_rows = cursor.fetchall()
        context['liabilities'] = [{
            'type': row[0],
            'balance': float(row[1]) if row[1] else 0,
            'apr': float(row[2]) if row[2] else 0,
            'minimum_payment': float(row[3]) if row[3] else 0,
            'credit_limit': float(row[4]) if row[4] else 0
        } for row in liability_rows]
        
        # 5. Recent Spending (last 3 months)
        cursor.execute("""
            SELECT month, total_income, total_expenses, net_cash_flow, top_category
            FROM spending_analytics 
            WHERE item_id = ?
            ORDER BY month DESC
        """, (item_uuid,))
        analytics_rows = cursor.fetchall()
        context['spending'] = [{
            'month': row[0].strftime('%Y-%m') if row[0] else None,
            'income': float(row[1]) if row[1] else 0,
            'expenses': float(row[2]) if row[2] else 0,
            'net': float(row[3]) if row[3] else 0,
            'top_category': row[4]
        } for row in analytics_rows[:3]]  # Last 3 months
        
        # 6. Calculate key metrics
        total_debt = sum(l['balance'] for l in context['liabilities'])
        total_income = sum(i['monthly'] for i in context['income'])
        total_min_payments = sum(l['minimum_payment'] for l in context['liabilities'])
        
        if total_income > 0:
            dti_ratio = (total_min_payments / total_income) * 100
        else:
            dti_ratio = 0
        
        # Calculate credit utilization
        total_credit_used = sum(l['balance'] for l in context['liabilities'] if l['type'] == 'Credit Card')
        total_credit_limit = sum(l['credit_limit'] for l in context['liabilities'] if l['type'] == 'Credit Card' and l['credit_limit'])
        
        if total_credit_limit > 0:
            credit_utilization = (total_credit_used / total_credit_limit) * 100
        else:
            credit_utilization = 0
        
        context['metrics'] = {
            'total_debt': round(total_debt, 2),
            'monthly_income': round(total_income, 2),
            'monthly_obligations': round(total_min_payments, 2),
            'dti_ratio': round(dti_ratio, 2),
            'total_balance': round(sum(a['balance'] for a in context['accounts']), 2),
            'credit_utilization': round(credit_utilization, 2)
        }
        
        conn.close()
        
        return jsonify(context)
        
    except Exception as e:
        tb = traceback.format_exc()
        return jsonify({"error": "context_fetch_failed", "exception": str(e), "trace": tb}), 500

@app.route("/chat", methods=["POST"])
def chat():
    """Multi-agent chatbot with conversation memory"""
    try:
        data = request.get_json() or {}
        item_id = data.get("item_id")
        message = data.get("message")
        session_id = data.get("session_id", item_id)  # Use item_id as default session
        
        if not item_id or not message:
            return jsonify({"error": "item_id and message required"}), 400
        
        # Process with orchestrator (now with memory)
        result = orchestrator.process_query(item_id, message, session_id)
        
        return jsonify(result)
        
    except Exception as e:
        tb = traceback.format_exc()
        return jsonify({
            "success": False,
            "error": "chat_failed",
            "exception": str(e),
            "trace": tb
        }), 500

@app.route("/clear_conversation", methods=["POST"])
def clear_conversation():
    """Clear conversation history for a session"""
    try:
        data = request.get_json() or {}
        session_id = data.get("session_id") or data.get("item_id")
        
        if session_id:
            orchestrator.clear_conversation(session_id)
            return jsonify({"success": True, "message": "Conversation cleared"})
        
        return jsonify({"error": "session_id required"}), 400
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# ----------------------------
# Health endpoint
# ----------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/chat_page")
def serve_chat():
    """Serve the chat interface page"""
    return send_from_directory("static", "chat.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)