# tools/user_profile_tools.py
from datetime import datetime
from db import get_connection

class UserProfileTools:
    """Fetch and format user profile information"""
    
    @staticmethod
    def get_user_profile(phone: str) -> dict:
        """
        Get complete user profile including personal info and accounts
        Returns: {
            "personal_info": {...},
            "accounts_summary": {...},
            "error": str (if any)
        }
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            profile = {}
            
            # 1. Personal Information
            cursor.execute("""
                SELECT 
                    full_name,
                    email,
                    date_of_birth,
                    address_street,
                    address_city,
                    address_state,
                    address_country,
                    address_zip
                FROM user_identity
                WHERE phone = ?
            """, (phone,))
            
            identity = cursor.fetchone()
            
            if identity:
                # 🔥 FIX: Calculate age from date_of_birth instead of birth_year
                date_of_birth = identity[2]  # This is a date object
                age = None
                birth_year = None
                
                if date_of_birth:
                    # Calculate age from date of birth
                    today = datetime.now()
                    birth_year = date_of_birth.year
                    age = today.year - date_of_birth.year
                    
                    # Adjust if birthday hasn't occurred yet this year
                    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
                        age -= 1
                
                profile['personal_info'] = {
                    'full_name': identity[0],
                    'email': identity[1],
                    'date_of_birth': date_of_birth.strftime('%Y-%m-%d') if date_of_birth else None,  # 🔥 NEW
                    'birth_year': birth_year,  # 🔥 DERIVED from date_of_birth
                    'age': age,
                    'phone': phone,
                    'address': {
                        'street': identity[3],
                        'city': identity[4],
                        'state': identity[5],
                        'country': identity[6],
                        'zip': identity[7]
                    },
                    'formatted_address': UserProfileTools._format_address(
                        identity[3], identity[4], identity[5], identity[6], identity[7]
                    )
                }
            else:
                # Fallback to basic user table
                cursor.execute("SELECT name FROM users WHERE phone = ?", (phone,))
                user = cursor.fetchone()
                profile['personal_info'] = {
                    'full_name': user[0] if user else 'Unknown',
                    'phone': phone,
                    'date_of_birth': None,
                    'birth_year': None,
                    'age': None,
                    'email': None,
                    'address': None
                }
            
            # 2. Accounts Summary
            cursor.execute("""
                SELECT 
                    account_number,
                    name,
                    type,
                    subtype,
                    mask,
                    balance_current,
                    balance_available,
                    is_primary,
                    status,
                    created_at
                FROM accounts
                WHERE phone = ?
                ORDER BY is_primary DESC, created_at ASC
            """, (phone,))
            
            accounts = cursor.fetchall()
            
            # Build accounts list first
            accounts_list = [{
                'account_number': row[0],
                'name': row[1],
                'type': row[2],
                'subtype': row[3],
                'mask': row[4],
                'balance_current': float(row[5]) if row[5] else 0,
                'balance_available': float(row[6]) if row[6] else 0,
                'is_primary': bool(row[7]),
                'status': row[8],
                'account_age_days': (datetime.now() - row[9]).days if row[9] else 0
            } for row in accounts]

            # Then find primary account
            primary_account = None
            if accounts_list:
                primary_account = next(
                    (acc for acc in accounts_list if acc['is_primary']),  # ✅ "acc" is properly defined
                    accounts_list[0]  # Fallback to first account
                )

            profile['accounts_summary'] = {
            'total_accounts': len(accounts),
            'accounts': accounts_list,
            'primary_account': primary_account
        }
                            
            return profile
            
        except Exception as e:
            print(f"❌ Error fetching user profile: {e}")
            import traceback
            traceback.print_exc()  # 🔥 Print full stack trace for debugging
            return {"error": str(e)}
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def _format_address(street, city, state, country, zip_code):
        """Format address into a readable string"""
        parts = []
        if street:
            parts.append(street)
        if city:
            parts.append(city)
        if state:
            parts.append(state)
        if zip_code:
            parts.append(zip_code)
        if country:
            parts.append(country)
        
        return ", ".join(parts) if parts else None
    
    @staticmethod
    def get_account_details(phone: str, account_number: str = None) -> dict:
        """
        Get detailed information about specific account(s)
        If account_number is None, returns primary account details
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            if account_number:
                cursor.execute("""
                    SELECT 
                        account_number, name, type, subtype, mask,
                        balance_current, balance_available, 
                        is_primary, status, created_at
                    FROM accounts
                    WHERE phone = ? AND account_number = ?
                """, (phone, account_number))
            else:
                # Get primary account
                cursor.execute("""
                    SELECT 
                        account_number, name, type, subtype, mask,
                        balance_current, balance_available, 
                        is_primary, status, created_at
                    FROM accounts
                    WHERE phone = ? AND is_primary = 1
                """, (phone,))
            
            account = cursor.fetchone()
            
            if not account:
                return {"error": "Account not found"}
            
            return {
                'account_number': account[0],
                'name': account[1],
                'type': account[2],
                'subtype': account[3],
                'mask': account[4],
                'balance_current': float(account[5]) if account[5] else 0,
                'balance_available': float(account[6]) if account[6] else 0,
                'is_primary': bool(account[7]),
                'status': account[8],
                'account_age_days': (datetime.now() - account[9]).days if account[9] else 0
            }
            
        except Exception as e:
            print(f"❌ Error fetching account details: {e}")
            return {"error": str(e)}
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def get_formatted_profile_summary(phone: str) -> str:
        """
        Get a human-readable profile summary for agent context
        """
        profile = UserProfileTools.get_user_profile(phone)
        
        if "error" in profile:
            return f"Error fetching profile: {profile['error']}"
        
        personal = profile.get('personal_info', {})
        accounts = profile.get('accounts_summary', {})
        
        summary = f"""
USER PROFILE:
Name: {personal.get('full_name', 'Unknown')}
Age: {personal.get('age', 'Unknown')}
Phone: {personal.get('phone', 'Unknown')}
Email: {personal.get('email', 'Not provided')}
Address: {personal.get('formatted_address', 'Not provided')}

ACCOUNTS:
Total Accounts: {accounts.get('total_accounts', 0)}
"""
        
        for acc in accounts.get('accounts', []):
            summary += f"\n  - {acc['name']} ({acc['subtype']}): ${acc['balance_current']:,.2f}"
            if acc['is_primary']:
                summary += " [PRIMARY]"
        
        return summary.strip()