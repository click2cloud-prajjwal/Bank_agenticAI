# tools/database_tools.py
from db import get_connection

class DatabaseTools:
    """Database query tools for agents - Phone-based authentication"""
    
    def get_user_context(self, phone: str) -> dict:
        """Get complete financial context for a user by phone number"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            context = {}
            
            # Verify user exists
            cursor.execute("SELECT phone, name FROM users WHERE phone = ?", (phone,))
            user = cursor.fetchone()
            if not user:
                return {"error": "user_not_found"}
            
            # 1. User Identity
            cursor.execute("""
                SELECT full_name, email, address_city, address_state
                FROM user_identity WHERE phone = ?
            """, (phone,))
            identity = cursor.fetchone()
            if identity:
                context['identity'] = {
                    'name': identity[0] or user[1],  # Fallback to users.name
                    'email': identity[1],
                    'city': identity[2],
                    'state': identity[3]
                }
            else:
                context['identity'] = {'name': user[1]}
            
            # 2. Accounts
            cursor.execute("""
                SELECT account_number, name, type, subtype, 
                       balance_current, balance_available, is_primary
                FROM accounts 
                WHERE phone = ? AND status = 'active'
                ORDER BY is_primary DESC, created_at ASC
            """, (phone,))
            
            accounts = cursor.fetchall()
            context['accounts'] = [{
                'account_number': row[0],
                'name': row[1],
                'type': row[2],
                'subtype': row[3],
                'balance': float(row[4]) if row[4] else 0,
                'available': float(row[5]) if row[5] else 0,
                'is_primary': bool(row[6])
            } for row in accounts]
            
            # 3. Recent Transactions (last 100)
            cursor.execute("""
                SELECT date, name, amount, category, merchant_name
                FROM transactions
                WHERE phone = ?
                ORDER BY date DESC
                OFFSET 0 ROWS FETCH NEXT 100 ROWS ONLY
            """, (phone,))
            
            transactions = cursor.fetchall()
            context['recent_transactions'] = [{
                'date': row[0].strftime('%Y-%m-%d') if row[0] else None,
                'description': row[1],
                'amount': float(row[2]) if row[2] else 0,
                'category': row[3],
                'merchant': row[4]
            } for row in transactions]
            
            # 4. Income
            cursor.execute("""
                SELECT employer_name, monthly_income, annual_income
                FROM user_income WHERE phone = ?
            """, (phone,))
            income = cursor.fetchall()
            
            if income:
                context['income'] = [{
                    'source': row[0],
                    'monthly': float(row[1]) if row[1] else 0,
                    'annual': float(row[2]) if row[2] else 0
                } for row in income]
            else:
                # Auto-detect from transactions (salary deposits)
                salary_txns = [
                    t for t in context.get('recent_transactions', [])
                    if t['amount'] < 0 and 'salary' in (t['description'] or '').lower()
                ]
                
                if salary_txns:
                    latest = salary_txns[0]
                    monthly_salary = abs(latest['amount'])
                    context['income'] = [{
                        'source': 'Auto-detected Salary',
                        'monthly': monthly_salary,
                        'annual': monthly_salary * 12
                    }]
                else:
                    context['income'] = []
            
            # 5. Liabilities
            cursor.execute("""
                SELECT liability_type, balance, minimum_payment, credit_limit
                FROM user_liabilities WHERE phone = ?
            """, (phone,))
            liabilities = cursor.fetchall()
            context['liabilities'] = [{
                'type': row[0],
                'balance': float(row[1]) if row[1] else 0,
                'min_payment': float(row[2]) if row[2] else 0,
                'limit': float(row[3]) if row[3] else 0
            } for row in liabilities]
            
            # 6. Spending Summary
            cursor.execute("""
                SELECT month, total_income, total_expenses, net_cash_flow
                FROM spending_analytics
                WHERE phone = ?
                ORDER BY month DESC
                OFFSET 0 ROWS FETCH NEXT 6 ROWS ONLY
            """, (phone,))
            spending = cursor.fetchall()
            context['spending_summary'] = [{
                'month': row[0].strftime('%Y-%m') if row[0] else None,
                'income': float(row[1]) if row[1] else 0,
                'expenses': float(row[2]) if row[2] else 0,
                'net': float(row[3]) if row[3] else 0
            } for row in spending]
            
            # 7. Calculate Summary Metrics
            total_debt = sum(l['balance'] for l in context['liabilities'])
            total_income = sum(i['monthly'] for i in context['income'])
            total_min_payments = sum(l['min_payment'] for l in context['liabilities'])
            
            dti_ratio = (total_min_payments / total_income * 100) if total_income > 0 else 0
            
            total_credit_used = sum(
                l['balance'] for l in context['liabilities'] 
                if l['type'] == 'Credit Card'
            )
            total_credit_limit = sum(
                l['limit'] for l in context['liabilities'] 
                if l['type'] == 'Credit Card' and l['limit']
            )
            credit_utilization = (
                (total_credit_used / total_credit_limit * 100) 
                if total_credit_limit > 0 else 0
            )
            
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