# agents/crm_agent.py
from agents.base_agent import BaseAgent
from tools.user_profile_tools import UserProfileTools
from tools.crm_tools import CRMTools
import json

class CRMAgent(BaseAgent):
    """Handles CRM functions: user profile queries, preferences, and customer relationship management"""
    
    def __init__(self):
        super().__init__(
            name="CRM Specialist",
            role="Customer Relationship & Profile Management Expert",
            instructions="""You are a CRM specialist for a banking assistant.

    Your primary responsibilities:
    1. Answer ALL questions about user's personal information
    2. Handle service requests and tickets
    3. Provide information about pre-approved offers
    4. Check customer flags (VIP, high risk, etc.)
    5. Review interaction history

    RESPONSE RULES:
    1. Be direct and concise
    2. Always confirm the information clearly
    3. End with "What else can I help you with?" wherever appropriate.
    4. Use the customer's first name naturally

    PERSONAL INFORMATION YOU CAN PROVIDE:
    - Full name, age, date of birth (DOB)
    - Email address, phone number
    - Physical address
    - Account numbers, types, subtypes

    CRM INFORMATION YOU CAN PROVIDE:
    - Service requests/tickets (open, resolved)
    - Interaction history (calls, chats, visits)
    - Pre-approved offers (loans, cards)
    - Customer flags (VIP, high risk, dormant)
    - Customer segment/tier

    EXAMPLES:

    User: "Do I have any open tickets?"
    Response: "Yes, you have 1 open ticket: Card Reissue (Critical Priority) created on Dec 2. The status is currently Open. What else can I help you with?"

    User: "Am I a VIP customer?"
    Response: "Yes, you're a VIP customer! You have Platinum tier status with us. What else can I help you with?"

    User: "Any offers for me?"
    Response: "Yes! You have 2 active pre-approved offers:
    1. Personal Loan up to $500,000 (expires Dec 31)
    2. Home Loan up to $5,000,000 (expires Jan 31)

    Would you like details on either? What else can I help you with?"

    User: "What did we discuss last time?"
    Response: "In your last interaction on Dec 2, you reported a lost credit card via chat. The card was blocked immediately and a replacement is being shipped. What else can I help you with?"

    CRITICAL RULES:
    - Answer EVERY question directly
    - Format amounts with $ sign and commas (e.g., $500,000)
    - For dates, use friendly format (e.g., "Dec 2" not "2025-12-02")
    - Always end with "What else can I help you with?"
    - Maximum 150 words per response"""
        )
        self.profile_tools = UserProfileTools()
        self.crm_tools = CRMTools()
    
    def process(self, context: dict, query: str, conversation_history: list = None) -> dict:
        """Process CRM and profile queries"""
        
        # Get user profile
        profile = context.get("profile", {})
        accounts = context.get("accounts", [])
        crm_data = context.get("crm", {})
        
        if not profile:
            return self.format_response(
                "I'm having trouble accessing your profile information right now. Please try again in a moment.",
                metadata={"error": "no_profile"}
            )
        
        # Extract all profile fields
        full_name = profile.get('full_name', '')
        first_name = full_name.split()[0] if full_name else ''
        age = profile.get('age')
        date_of_birth = profile.get('date_of_birth')
        email = profile.get('email')
        phone = profile.get('phone')
        address = profile.get('address', {})
        
        # Format date of birth nicely
        formatted_dob = None
        if date_of_birth:
            try:
                from datetime import datetime
                dob_obj = datetime.strptime(date_of_birth, '%Y-%m-%d')
                formatted_dob = dob_obj.strftime('%B %d, %Y')  # "May 15, 1997"
            except:
                formatted_dob = date_of_birth
        
        # Build conversation context
        conversation_context = ""
        if conversation_history:
            recent = conversation_history[-2:]
            conversation_context = "RECENT CONVERSATION:\n"
            for exchange in recent:
                conversation_context += f"User: {exchange['user_query']}\n"
                conversation_context += f"Assistant: {exchange['bot_response'][:100]}...\n"
            conversation_context += "\n"
        
        # Analyze query type
        query_lower = query.lower()
        
        query_type = "general_profile"
        if any(w in query_lower for w in ["date of birth", "dob", "birth date", "birthdate", "birthday", "when was i born"]):
            query_type = "date_of_birth"
        elif any(w in query_lower for w in ["how old", "my age", "what is my age", "age"]):
            query_type = "age"
        elif any(w in query_lower for w in ["email", "e-mail", "mail address"]):
            query_type = "email"
        elif any(w in query_lower for w in ["phone", "number", "mobile", "contact"]):
            query_type = "phone"
        elif any(w in query_lower for w in ["address", "where do i live", "location", "city", "state"]):
            query_type = "address"
        elif any(w in query_lower for w in ["my name", "what is my name", "who am i"]):
            query_type = "name"
        elif any(w in query_lower for w in ["account number", "account numbers", "accounts list"]):
            query_type = "account_numbers"
        elif any(w in query_lower for w in ["account type", "types of account", "what accounts", "account subtype"]):
            query_type = "account_types"
        elif any(w in query_lower for w in ["primary account", "main account"]):
            query_type = "primary_account"
        elif any(w in query_lower for w in ["profile", "my information", "my details", "complete profile", "all information"]):
            query_type = "full_profile"
        elif any(w in query_lower for w in ["ticket", "complaint", "service request", "open issue"]):
            query_type = "service_requests"
        elif any(w in query_lower for w in ["vip", "tier", "segment", "status", "customer type"]):
            query_type = "customer_flags"
        elif any(w in query_lower for w in ["offer", "pre-approved", "loan offer", "card offer", "eligible"]):
            query_type = "offers"
        elif any(w in query_lower for w in ["last time", "previous", "interaction", "what did we", "history"]):
            query_type = "interaction_history"
        
        # Prepare data summary for LLM
        data_summary = f"""
{conversation_context}

CUSTOMER PROFILE:
Full Name: {full_name or 'Not provided'}
First Name: {first_name or 'Not provided'}
Age: {age if age else 'Not provided'}
Date of Birth: {formatted_dob if formatted_dob else 'Not provided'}
Date of Birth (ISO): {date_of_birth if date_of_birth else 'Not provided'}
Email: {email or 'Not provided'}
Phone: {phone or 'Not provided'}

Address:
{json.dumps(address, indent=2) if address else 'Not provided'}

ACCOUNTS ({len(accounts)} total):
{json.dumps([{
    'account_number': a.get('account_number'),
    'name': a.get('name'),
    'type': a.get('type'),
    'subtype': a.get('subtype'),
    'is_primary': a.get('is_primary', False)
} for a in accounts], indent=2) if accounts else 'No accounts'}

CRM DATA:
Service Requests: {json.dumps(crm_data.get('service_requests', []), indent=2)}
Recent Interactions: {json.dumps(crm_data.get('interactions', [])[:5], indent=2)}
Active Offers: {json.dumps(crm_data.get('offers', []), indent=2)}
Customer Flags: {json.dumps(crm_data.get('flags', []), indent=2)}
CRM Summary: {json.dumps(crm_data.get('crm_summary', {}), indent=2)}

QUERY TYPE DETECTED: {query_type}

CUSTOMER QUESTION: {query}

Provide a clear, direct answer using the data above. Use the customer's first name naturally. End with "What else can I help you with?"
"""
        
        messages = [
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": data_summary}
        ]
        
        response = self.call_llm(messages, temperature=0.5)
        
        if response["type"] == "error":
            return self.format_response(
                f"I'm having trouble accessing your information right now{', ' + first_name if first_name else ''}. Could you try again?",
                metadata={"error": "llm_error"}
            )
        
        return self.format_response(
            content=response["content"],
            metadata={
                "query_type": query_type,
                "user_name": full_name,
                "has_profile": bool(profile),
                "accounts_count": len(accounts)
            }
        )