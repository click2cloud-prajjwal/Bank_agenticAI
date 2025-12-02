# agents/orchestrator.py - Updated for Phone-based Authentication
from agents.router_agent import RouterAgent
from agents.account_agent import AccountAgent
from agents.transaction_agent import TransactionAgent
from agents.financial_advisor_agent import FinancialAdvisorAgent
from agents.analytics_agent import AnalyticsAgent
from agents.crm_agent import CRMAgent
from tools.database_tools import DatabaseTools

class Orchestrator:
    """Coordinates all agents with conversation memory - Phone-based"""

    def __init__(self):
        self.router = RouterAgent()
        self.agents = {
            "ACCOUNT_QUERY": AccountAgent(),
            "TRANSACTION_QUERY": TransactionAgent(),
            "FINANCIAL_ADVICE": FinancialAdvisorAgent(),
            "ANALYTICS": AnalyticsAgent(),
            "CRM_QUERY": CRMAgent() 
        }
        self.db_tools = DatabaseTools()
        # Store conversation history per session
        self.conversations = {}  # {session_id: [messages]}

    def process_query(self, phone: str, query: str, session_id: str = None) -> dict:
        """Process query with conversation memory using phone number"""
        
        # Use phone as session_id if not provided
        if not session_id:
            session_id = phone
        
        # Initialize conversation history for this session
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        
        # Retrieve user context by phone number
        context = self.db_tools.get_user_context(phone)

        if "error" in context:
            return {
                "success": False,
                "error": context["error"],
                "response": "We were unable to access your account information. Please try logging in again."
            }

        #VERIFICATION: Ensure profile data exists in context
        if 'profile' not in context or not context['profile']:
            print(f"⚠️ Warning: Profile data missing for {phone}")
            # Add minimal profile data as fallback
            context['profile'] = {
                'phone': phone,
                'full_name': 'Valued Customer',
                'age': None,
                'email': None,
                'address': None
            }

        # Get conversation history
        conversation_history = self.conversations[session_id]
        
        # Check if user is ending conversation
        is_ending = self._is_conversation_ender(query.lower())
        
        # Check if this is a follow-up (short response like "yes", "why", etc.)
        is_followup = self._is_followup_query(query, conversation_history)
        
        # If it's a follow-up, enhance the query with context
        enhanced_query = query
        if is_followup and conversation_history:
            last_exchange = conversation_history[-1]
            enhanced_query = f"[Previous question: {last_exchange['user_query']}]\n[Previous response: {last_exchange['bot_response'][:200]}...]\n[User's follow-up: {query}]"
        
        # Step 1: Route the query
        if is_ending:
            intent = "GENERAL"
            confidence = 1.0
        else:
            routing = self.router.process(context, enhanced_query if is_followup else query)
            intent_data = routing.get("metadata", {})
            intent = intent_data.get("intent", "GENERAL")
            confidence = intent_data.get("confidence", 0.0)

            # If it's a follow-up, use the same agent as last time
            if is_followup and conversation_history:
                last_agent = conversation_history[-1].get('agent_used')
                if last_agent and last_agent != "General Assistant":
                    intent = self._get_intent_for_agent(last_agent)

        # Step 2: Process based on intent
        if intent == "GENERAL":
            response_text = self._handle_general(query, context, conversation_history)
            agent_used = "General Assistant"

        elif intent in self.agents:
            agent = self.agents[intent]
            # Pass conversation history to agent
            agent_response = agent.process(context, query, conversation_history)
            response_text = agent_response.get("content", "We were unable to process your request.")
            agent_used = agent.name

        else:
            response_text = "Your request could not be categorized. Please rephrase the question."
            agent_used = "Fallback"

        # Store this exchange in conversation history
        self.conversations[session_id].append({
            "user_query": query,
            "bot_response": response_text,
            "agent_used": agent_used,
            "intent": intent
        })
        
        # Keep only last 10 exchanges to manage memory
        if len(self.conversations[session_id]) > 10:
            self.conversations[session_id] = self.conversations[session_id][-10:]

        return {
            "success": True,
            "query": query,
            "intent": intent,
            "confidence": confidence,
            "agent_used": agent_used,
            "response": response_text,
            "context_summary": {
                "accounts": len(context.get("accounts", [])),
                "transactions": len(context.get("recent_transactions", [])),
                "total_balance": context.get("summary", {}).get("total_balance", 0)
            },
            "is_followup": is_followup,
            "is_ending": is_ending
        }

    def _is_followup_query(self, query: str, history: list) -> bool:
        """Check if this is a follow-up to previous conversation"""
        if not history:
            return False
        
        query_lower = query.lower().strip()
        
        # Check if it's a conversation ender first
        if self._is_conversation_ender(query_lower):
            return False
        
        # Positive follow-up responses
        followup_patterns = [
            "yes", "yeah", "yep", "sure", "ok", "okay",
            "why", "how", "what", "when", "where",
            "tell me", "explain", "details", "more",
            "go ahead", "continue", "and", "also",
            "please", "can you"
        ]
        
        # Check if query is very short (likely a follow-up)
        if len(query.split()) <= 4:
            for pattern in followup_patterns:
                if query_lower.startswith(pattern) or query_lower == pattern:
                    return True
        
        return False

    def _is_conversation_ender(self, query: str) -> bool:
        """Check if user is ending the conversation"""
        query_lower = query.lower().strip()
        
        enders = [
            "no", "nope", "nah", "no thanks", "no thank you",
            "nothing", "nothing else", "that's all", "that's it",
            "i'm good", "im good", "all good", "we're good",
            "thanks", "thank you", "bye", "goodbye"
        ]
        
        # Exact matches for short responses
        if query_lower in enders:
            return True
        
        # Starts with common enders
        for ender in ["no,", "nope,", "nothing,", "that's all", "thanks,"]:
            if query_lower.startswith(ender):
                return True
        
        return False
    
    def _get_intent_for_agent(self, agent_name: str) -> str:
        """Map agent name back to intent"""
        agent_to_intent = {
            "Account Specialist": "ACCOUNT_QUERY",
            "Transaction Analyst": "TRANSACTION_QUERY",
            "Financial Advisor": "FINANCIAL_ADVICE",
            "Analytics Specialist": "ANALYTICS",
            "CRM Specialist": "CRM_QUERY"
        }
        return agent_to_intent.get(agent_name, "GENERAL")

    def _handle_general(self, query: str, context: dict, history: list) -> str:
        """Handle general queries - greetings, help, thanks"""
        query_lower = query.lower()
        
        profile = context.get("profile", {})
        full_name = profile.get('full_name', '')
        first_name = full_name.split()[0] if full_name and full_name != 'Valued Customer' else ''
        greeting_name = f" {first_name}" if first_name else ""

        # Conversation enders
        if self._is_conversation_ender(query_lower):
            return f"Great{greeting_name}! If you need anything else, just let me know. Have a good day!"

        # Follow-up handling
        if history and any(word in query_lower for word in ["yes", "sure", "ok", "yeah"]):
            last_response = history[-1].get('bot_response', '').lower()
            if 'help' in last_response or 'assist' in last_response:
                return (
                    f"I can help you with account balances, recent transactions, spending analysis, "
                    f"financial advice, and your personal profile. What would you like to know{greeting_name}?"
                )

        # Greetings
        if any(w in query_lower for w in ["hello", "hi", "hey", "good morning", "good afternoon"]):
            greeting = f"Hello{greeting_name}!" if first_name else "Hello!"
            return f"{greeting} How can I assist you today?"

        # Help/Capabilities
        elif any(w in query_lower for w in ["help", "what can you do", "capabilities", "how can you help"]):
            return (
                f"I can help you{greeting_name} with:\n"
                f"• Account balances and status\n"
                f"• Transaction history and spending\n"
                f"• Financial advice and loan eligibility\n"
                f"• Spending analytics and trends\n"
                f"• Your personal profile and information\n\n"
                f"What would you like to know?"
            )

        # Thanks
        elif any(w in query_lower for w in ["thank", "thanks", "appreciate"]):
            return f"You're welcome{greeting_name}! Let me know if you need anything else."

        # Default
        return (
            f"I'm here to help with your finances{greeting_name}. Ask me about your accounts, "
            f"transactions, spending, financial advice, or your profile information."
        )
    def clear_conversation(self, session_id: str):
        """Clear conversation history for a session"""
        if session_id in self.conversations:
            del self.conversations[session_id]