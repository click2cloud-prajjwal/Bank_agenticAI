# tools/database_tools.py
from db import get_connection

class DatabaseTools:
    """Database query tools for agents"""
    
    def get_user_context(self, item_id: str) -> dict:
        """Get complete financial context for a user"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            context = {}
            
            # Get item UUID
            cursor.execute("SELECT item_id FROM items WHERE plaid_item_id = ?", (item_id,))
            row = cursor.fetchone()
            if not row:
                return {"error": "item_not_found"}
            item_uuid = row[0]
            
            # Identity
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
            
            # Accounts - FIX: Specify table alias for 'name'
            cursor.execute("""
                SELECT a.name, a.type, a.subtype, a.balance_current, a.balance_available
                FROM accounts a WHERE a.item_id = ?
            """, (item_uuid,))
            accounts = cursor.fetchall()
            context['accounts'] = [{
                'name': row[0],
                'type': row[1],
                'subtype': row[2],
                'balance': float(row[3]) if row[3] else 0,
                'available': float(row[4]) if row[4] else 0
            } for row in accounts]
            
            # Recent transactions - FIX: Specify table aliases
            cursor.execute("""
                SELECT t.date, t.name, t.amount, t.category
                FROM transactions t
                JOIN accounts a ON t.account_id = a.account_id
                WHERE a.item_id = ?
                ORDER BY t.date DESC
            """, (item_uuid,))
            transactions = cursor.fetchall()
            context['recent_transactions'] = [{
                'date': row[0].strftime('%Y-%m-%d') if row[0] else None,
                'description': row[1],
                'amount': float(row[2]) if row[2] else 0,
                'category': row[3]
            } for row in transactions]
            
            # Income
            cursor.execute("""
                SELECT employer_name, monthly_income, annual_income
                FROM user_income WHERE item_id = ?
            """, (item_uuid,))
            income = cursor.fetchall()
            context['income'] = [{
                'source': row[0],
                'monthly': float(row[1]) if row[1] else 0,
                'annual': float(row[2]) if row[2] else 0
            } for row in income]
            
            # Liabilities
            cursor.execute("""
                SELECT liability_type, balance, minimum_payment, credit_limit
                FROM user_liabilities WHERE item_id = ?
            """, (item_uuid,))
            liabilities = cursor.fetchall()
            context['liabilities'] = [{
                'type': row[0],
                'balance': float(row[1]) if row[1] else 0,
                'min_payment': float(row[2]) if row[2] else 0,
                'limit': float(row[3]) if row[3] else 0
            } for row in liabilities]
            
            # Spending summary
            cursor.execute("""
                SELECT month, total_income, total_expenses, net_cash_flow
                FROM spending_analytics
                WHERE item_id = ?
                ORDER BY month DESC
            """, (item_uuid,))
            spending = cursor.fetchall()
            context['spending_summary'] = [{
                'month': row[0].strftime('%Y-%m') if row[0] else None,
                'income': float(row[1]) if row[1] else 0,
                'expenses': float(row[2]) if row[2] else 0,
                'net': float(row[3]) if row[3] else 0
            } for row in spending]
            
            # Calculate summary metrics
            total_debt = sum(l['balance'] for l in context['liabilities'])
            total_income = sum(i['monthly'] for i in context['income'])
            total_min_payments = sum(l['min_payment'] for l in context['liabilities'])
            
            dti_ratio = (total_min_payments / total_income * 100) if total_income > 0 else 0
            
            total_credit_used = sum(l['balance'] for l in context['liabilities'] if l['type'] == 'Credit Card')
            total_credit_limit = sum(l['limit'] for l in context['liabilities'] if l['type'] == 'Credit Card' and l['limit'])
            credit_utilization = (total_credit_used / total_credit_limit * 100) if total_credit_limit > 0 else 0
            
            context['summary'] = {
                'total_balance': round(sum(a['balance'] for a in context['accounts']), 2),
                'total_available': round(sum(a['available'] for a in context['accounts']), 2),
                'account_count': len(context['accounts'])
            }
            
            context['metrics'] = {
                'total_debt': round(total_debt, 2),
                'monthly_income': round(total_income, 2),
                'monthly_obligations': round(total_min_payments, 2),
                'dti_ratio': round(dti_ratio, 2),
                'credit_utilization': round(credit_utilization, 2)
            }
            
            return context
            
        except Exception as e:
            print(f"❌ Database error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
        finally:
            conn.close()