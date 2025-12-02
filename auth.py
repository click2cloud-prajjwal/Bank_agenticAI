# auth.py
import secrets
from datetime import datetime, timedelta
from db import get_connection

class AuthService:
    """Handle phone + MPIN authentication"""
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normalize phone number to digits only"""
        # Remove all non-digit characters
        return ''.join(filter(str.isdigit, phone))
    
    @staticmethod
    def authenticate(phone: str, mpin: str) -> dict:
        """
        Authenticate user with phone number and MPIN
        Returns: {"success": True/False, "phone": str, "name": str, "error": str}
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Normalize the input phone number to digits only
            phone_normalized = AuthService.normalize_phone(phone)
            
            # Try to find user by matching normalized phone numbers
            cursor.execute("""
                SELECT phone, mpin, name, is_active, failed_login_attempts
                FROM users
            """)
            
            all_users = cursor.fetchall()
            user = None
            actual_phone = None
            
            # Find matching user by comparing normalized phone numbers
            for db_phone, db_mpin, db_name, db_active, db_failed in all_users:
                db_phone_normalized = AuthService.normalize_phone(db_phone)
                if db_phone_normalized == phone_normalized:
                    user = (db_phone, db_mpin, db_name, db_active, db_failed)
                    actual_phone = db_phone  # Use the actual format from DB
                    break
            
            if not user:
                return {
                    "success": False,
                    "error": "Phone number not found. Please check your number."
                }
            
            db_phone, db_mpin, name, is_active, failed_attempts = user
            
            # Check if account is locked
            if failed_attempts >= 5:
                return {
                    "success": False,
                    "error": "Account locked due to too many failed attempts. Please contact support."
                }
            
            # Check if account is active
            if not is_active:
                return {
                    "success": False,
                    "error": "Account is inactive. Please contact support."
                }
            
            # Verify MPIN (plain text comparison for now)
            # ⚠️ TODO: Implement bcrypt hashing in production
            if db_mpin != mpin:
                # Increment failed attempts using actual_phone from DB
                cursor.execute("""
                    UPDATE users
                    SET failed_login_attempts = failed_login_attempts + 1
                    WHERE phone = ?
                """, (actual_phone,))
                conn.commit()
                
                remaining = 5 - (failed_attempts + 1)
                return {
                    "success": False,
                    "error": f"Incorrect MPIN. {remaining} attempts remaining."
                }
            
            # Success - Reset failed attempts and update last login
            cursor.execute("""
                UPDATE users
                SET failed_login_attempts = 0,
                    last_login = SYSUTCDATETIME()
                WHERE phone = ?
            """, (actual_phone,))
            conn.commit()
            
            # Log successful login
            AuthService.log_audit(actual_phone, "LOGIN_SUCCESS", f"User {name} logged in")
            
            return {
                "success": True,
                "phone": actual_phone,  # Return the actual phone format from DB
                "name": name,
                "message": "Login successful!"
            }
            
        except Exception as e:
            print(f"❌ Auth error: {e}")
            return {
                "success": False,
                "error": f"Authentication error: {str(e)}"
            }
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def create_session(phone: str, ip_address: str = None, user_agent: str = None) -> str:
        """Create a session for authenticated user"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Generate session ID
            session_id = secrets.token_urlsafe(32)
            
            # Session expires in 24 hours
            expires_at = datetime.now() + timedelta(hours=24)
            
            # Get primary account for this user
            cursor.execute("""
                SELECT account_number
                FROM accounts
                WHERE phone = ? AND is_primary = 1
            """, (phone,))
            
            account_row = cursor.fetchone()
            selected_account = account_row[0] if account_row else None
            
            # Create session
            cursor.execute("""
                INSERT INTO sessions (
                    session_id, phone, selected_account,
                    ip_address, user_agent, expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, phone, selected_account, ip_address, user_agent, expires_at))
            
            conn.commit()
            
            return session_id
            
        except Exception as e:
            print(f"❌ Session creation error: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def verify_session(session_id: str) -> dict:
        """Verify if session is valid"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT s.phone, s.expires_at, u.name, s.selected_account
                FROM sessions s
                JOIN users u ON s.phone = u.phone
                WHERE s.session_id = ?
                AND s.expires_at > SYSUTCDATETIME()
                AND u.is_active = 1
            """, (session_id,))
            
            session = cursor.fetchone()
            
            if not session:
                return {"valid": False, "error": "Invalid or expired session"}
            
            phone, expires_at, name, account = session
            
            # Update last activity
            cursor.execute("""
                UPDATE sessions
                SET last_activity = SYSUTCDATETIME()
                WHERE session_id = ?
            """, (session_id,))
            conn.commit()
            
            return {
                "valid": True,
                "phone": phone,
                "name": name,
                "account": account
            }
            
        except Exception as e:
            print(f"❌ Session verification error: {e}")
            return {"valid": False, "error": str(e)}
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def logout(session_id: str):
        """Delete session on logout"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Get phone before deleting
            cursor.execute("SELECT phone FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            
            if row:
                phone = row[0]
                AuthService.log_audit(phone, "LOGOUT", f"User logged out")
            
            # Delete session
            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            
        except Exception as e:
            print(f"❌ Logout error: {e}")
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def log_audit(phone: str, action_type: str, details: str, ip_address: str = None):
        """Log user actions for audit"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO audit_log (phone, action_type, details, ip_address)
                VALUES (?, ?, ?, ?)
            """, (phone, action_type, details, ip_address))
            conn.commit()
        except Exception as e:
            print(f"⚠️ Audit log error: {e}")
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def get_user_accounts(phone: str) -> list:
        """Get all accounts for a user"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    account_number, name, type, subtype, mask,
                    balance_available, balance_current, is_primary, status
                FROM accounts
                WHERE phone = ?
                ORDER BY is_primary DESC, created_at ASC
            """, (phone,))
            
            accounts = cursor.fetchall()
            
            return [{
                "account_number": row[0],
                "name": row[1],
                "type": row[2],
                "subtype": row[3],
                "mask": row[4],
                "balance_available": float(row[5]) if row[5] else 0,
                "balance_current": float(row[6]) if row[6] else 0,
                "is_primary": bool(row[7]),
                "status": row[8]
            } for row in accounts]
            
        except Exception as e:
            print(f"❌ Error fetching accounts: {e}")
            return []
        finally:
            cursor.close()
            conn.close()