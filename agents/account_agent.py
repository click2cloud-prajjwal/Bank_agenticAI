# agents/account_agent.py
import json
from agents.base_agent import BaseAgent
from tools.database_tools import DatabaseTools
from tools.user_profile_tools import UserProfileTools

class AccountAgent(BaseAgent):
    """Handles account queries with voice-optimized short responses"""
    
    def __init__(self):
        super().__init__(
            name="Account Specialist",
            role="Account Information Expert",
            instructions="""You are an account specialist for a VOICE-based banking assistant.

Keep responses SHORT and CONVERSATIONAL like a phone call.

PERSONALIZATION:
- Use the customer's first name when appropriate
- Consider their age for age-appropriate advice
- Reference their location if relevant
- Make responses feel personal and warm

RESPONSE RULES:
1. Answer in 1-2 sentences
2. Give exact numbers clearly
3. Only mention important details
4. Sound natural, not robotic
5. Max 40 words for simple queries
6. After answering, end with "Anything else?" wherever required only. - NO follow-up questions

EXAMPLES:

User: "What's my balance?"
Response: "Your total balance across all accounts is $15,750. That's $2,450 in checking, $10,000 in savings, and $3,300 in your money market account. Anything else?"

User: "How much do I have available?"
Response: "You have $14,200 available to spend right now. There's about $1,550 in pending transactions that will clear in the next day or two. What else can I help you with?"

User: "Do I have enough for rent?"
Response: "Yes, your checking account has $2,450 available, so you're good for your $1,200 rent payment. That'll leave you with about $1,250 after it clears. Anything else?"

User: "Why is my balance low?"
Response: "Your checking is at $125 right now because rent and your credit card payment both cleared this week. Your paycheck should deposit on Friday. Do you have any other questions?"

User: "What's in my savings?"
Response: "Your savings account has $10,000 with all of it available. No pending transactions on that account. What else would you like to know?"

User: "Check my checking account"
Response: "Your checking account shows $2,450 current balance with $2,350 available. The $100 difference is from pending transactions. Anything else?"

CRITICAL RULES:
- Keep it brief, clear, and conversational
- After providing account info, ALWAYS end with "Anything else?" or "What else can I help you with?" or "Do you have any other questions?"
- DO NOT ask follow-up questions like "Would you like to see transactions?" or "Should I check other accounts?"
- DO NOT offer additional services unprompted
- Just answer their question clearly, then ask if they need anything else
- Maximum 40-50 words per response"""
        )
        self.db_tools = DatabaseTools()
        self.profile_tools = UserProfileTools()

    def process(self, context: dict, query: str, conversation_history: list = None) -> dict:
        """Process account queries with short responses"""
        
        profile = context.get("profile", {})
        user_name = profile.get('full_name', '')
        first_name = user_name.split()[0] if user_name else ''
        age = profile.get('age')
        email = profile.get('email')
        address = profile.get('address', {})

        accounts = context.get("accounts", [])
        summary = context.get("summary", {})
        recent_transactions = context.get("recent_transactions", [])
        
        if not accounts:
            return self.format_response(
                f"{'Hi ' + first_name + '! ' if first_name else ''}I don't see any connected accounts. You'll need to link your bank first.",
                metadata={"error": "no_accounts"}
            )
        
        total_balance = summary.get('total_balance', 0)
        total_available = summary.get('total_available', 0)
        pending_amount = total_balance - total_available
        
        # Check for low balances
        warnings = []
        checking_accounts = [a for a in accounts if 'checking' in a.get('subtype', '').lower()]
        for acc in checking_accounts:
            if acc.get('available', 0) < 200:
                warnings.append(f"{acc['name']} is low at ${acc['available']:.0f}")
        
        # Build conversation context
        conversation_context = ""
        if conversation_history:
            recent = conversation_history[-2:]
            conversation_context = "RECENT CONVERSATION:\n"
            for exchange in recent:
                conversation_context += f"User: {exchange['user_query']}\n"
                conversation_context += f"Assistant: {exchange['bot_response'][:100]}...\n"
            conversation_context += "\n"
        
        data_summary = f"""
{conversation_context}

CUSTOMER PROFILE:
Name: {user_name or 'Not provided'}
First Name: {first_name or 'Not provided'}
Age: {age or 'Unknown'}
Email: {email or 'Not provided'}
Location: {address.get('city', 'Unknown')}, {address.get('state', 'Unknown')}

ACCOUNT INFO:
Total Balance: ${total_balance:,.0f}
Available: ${total_available:,.0f}
Pending: ${pending_amount:,.0f}

Accounts ({len(accounts)} total):
{json.dumps([{
    'name': a['name'],
    'account_number': a.get('account_number', 'N/A'),
    'type': a['subtype'],
    'balance': f"${a['balance']:.0f}",
    'available': f"${a['available']:.0f}",
    'is_primary': a.get('is_primary', False)
} for a in accounts], indent=2)}

{"⚠️ LOW BALANCE WARNINGS: " + ", ".join(warnings) if warnings else "All accounts healthy"}

Recent Activity: {len(recent_transactions)} transactions

CUSTOMER QUESTION: {query}

Give a SHORT, DIRECT answer (1-2 sentences, max 40 words). Use their first name "{first_name}" naturally if appropriate. Sound like a friendly bank teller on the phone."""
        
        messages = [
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": data_summary}
        ]
        
        response = self.call_llm(messages, temperature=0.5)
        
        if response["type"] == "error":
            return self.format_response(
                 f"{'Hi ' + first_name + '! ' if first_name else ''}I can't access your accounts right now. Give me a moment and try again.",
                metadata={"error": "llm_error"}
            )
        
        return self.format_response(
            content=response["content"],
            metadata={
                "accounts_analyzed": len(accounts),
                "total_balance": total_balance,
                "warnings": warnings,
                "user_name": user_name,
                 "user_age": age
            }
        )