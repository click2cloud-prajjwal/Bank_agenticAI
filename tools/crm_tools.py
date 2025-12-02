# tools/crm_tools.py
from db import get_connection
from datetime import datetime

class CRMTools:
    """Tools to fetch CRM-specific data"""
    
    @staticmethod
    def get_crm_data(phone: str) -> dict:
        """
        Get all CRM data for a customer
        Returns: {
            "service_requests": [...],
            "interactions": [...],
            "offers": [...],
            "flags": [...],
            "crm_summary": {...}
        }
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            crm_data = {}
            
            # 1. Service Requests
            cursor.execute("""
                SELECT 
                    ticket_id, issue_type, description, status, priority,
                    created_at, updated_at, resolved_at
                FROM crm_service_requests
                WHERE phone = ?
                ORDER BY created_at DESC
            """, (phone,))
            
            requests = cursor.fetchall()
            crm_data['service_requests'] = [{
                'ticket_id': str(row[0]),
                'issue_type': row[1],
                'description': row[2],
                'status': row[3],
                'priority': row[4],
                'created_at': row[5].strftime('%Y-%m-%d %H:%M:%S') if row[5] else None,
                'updated_at': row[6].strftime('%Y-%m-%d %H:%M:%S') if row[6] else None,
                'resolved_at': row[7].strftime('%Y-%m-%d %H:%M:%S') if row[7] else None
            } for row in requests]
            
            # 2. Interactions (last 10)
            cursor.execute("""
                SELECT TOP 10
                    interaction_id, channel, summary, agent_name, sentiment, created_at
                FROM crm_interactions
                WHERE phone = ?
                ORDER BY created_at DESC
            """, (phone,))
            
            interactions = cursor.fetchall()
            crm_data['interactions'] = [{
                'interaction_id': str(row[0]),
                'channel': row[1],
                'summary': row[2],
                'agent_name': row[3],
                'sentiment': row[4],
                'created_at': row[5].strftime('%Y-%m-%d %H:%M:%S') if row[5] else None
            } for row in interactions]
            
            # 3. Active Offers
            cursor.execute("""
                SELECT 
                    offer_id, offer_type, preapproved_amount, 
                    eligibility_score, expiry_date, created_at
                FROM crm_offers
                WHERE phone = ? AND expiry_date >= CAST(GETDATE() AS DATE)
                ORDER BY expiry_date ASC
            """, (phone,))
            
            offers = cursor.fetchall()
            crm_data['offers'] = [{
                'offer_id': str(row[0]),
                'offer_type': row[1],
                'preapproved_amount': float(row[2]) if row[2] else 0,
                'eligibility_score': row[3],
                'expiry_date': row[4].strftime('%Y-%m-%d') if row[4] else None,
                'created_at': row[5].strftime('%Y-%m-%d %H:%M:%S') if row[5] else None
            } for row in offers]
            
            # 4. Active Flags
            cursor.execute("""
                SELECT 
                    flag_id, flag_type, notes, created_at
                FROM crm_flags
                WHERE phone = ? AND active = 1
                ORDER BY created_at DESC
            """, (phone,))
            
            flags = cursor.fetchall()
            crm_data['flags'] = [{
                'flag_id': str(row[0]),
                'flag_type': row[1],
                'notes': row[2],
                'created_at': row[3].strftime('%Y-%m-%d %H:%M:%S') if row[3] else None
            } for row in flags]
            
            # 5. CRM Summary
            open_tickets = len([r for r in crm_data['service_requests'] 
                               if r['status'] in ['Open', 'In Progress']])
            active_offers = len(crm_data['offers'])
            is_vip = any(f['flag_type'] == 'VIP' for f in crm_data['flags'])
            
            crm_data['crm_summary'] = {
                'total_service_requests': len(crm_data['service_requests']),
                'open_tickets': open_tickets,
                'total_interactions': len(crm_data['interactions']),
                'active_offers': active_offers,
                'total_flags': len(crm_data['flags']),
                'is_vip': is_vip,
                'last_interaction': crm_data['interactions'][0]['created_at'] if crm_data['interactions'] else None
            }
            
            return crm_data
            
        except Exception as e:
            print(f"❌ Error fetching CRM data: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
        finally:
            cursor.close()
            conn.close()