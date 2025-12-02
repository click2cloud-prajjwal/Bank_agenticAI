# agents/router_agent.py
from agents.base_agent import BaseAgent
import json

class RouterAgent(BaseAgent):
    """Routes queries to appropriate specialist agents with enhanced classification"""
    
    def __init__(self):
        super().__init__(
            name="Router",
            role="Intent Classifier",
            instructions="""You are an advanced intent classification system for a banking assistant.

Your responsibility is to accurately classify customer queries into ONE of these categories:

1. ACCOUNT_QUERY – Balance inquiries, account status, available funds, account health
   Examples: "What's my balance?", "How much do I have?", "Show my accounts"

2. TRANSACTION_QUERY – Transaction history, spending analysis, purchase details, merchant queries
   Examples: "Show my transactions", "What did I spend on groceries?", "Find that Amazon charge"

3. FINANCIAL_ADVICE – Loan eligibility, affordability checks, financial planning, debt management
   Examples: "Can I afford a car?", "Am I eligible for a loan?", "Should I pay off debt?"

4. ANALYTICS – Trends, patterns, comparisons, projections, spending insights
   Examples: "How's my spending trending?", "Compare this month to last", "Where is my money going?"

5. 5. CRM_QUERY – Personal information, profile queries, account metadata (NOT balances), customer preferences, SERVICE REQUESTS, OFFERS, FLAGS
   Examples: "What is my email?", "Show my account numbers", "Do I have any open tickets?", "Am I a VIP?", "Any offers for me?"

6. GENERAL – Greetings, capabilities, unclear queries, general help
   Examples: "Hello", "What can you do?", "Help me"

CLASSIFICATION RULES:
- FINANCIAL_ADVICE: Use this for ANY question about affordability, eligibility, or "can I afford"
- ANALYTICS: Use this for trends, comparisons, patterns, or "why" questions about spending
- TRANSACTION_QUERY: Use this for specific transaction lookups or merchant-specific queries
- ACCOUNT_QUERY: Use this only for simple balance/account status questions
- If query mentions BOTH transactions AND trends, choose ANALYTICS
- If query asks about loan/mortgage/car affordability, choose FINANCIAL_ADVICE
- If query asks "why" about spending patterns, choose ANALYTICS

CLASSIFICATION RULES FOR CRM_QUERY:
- Use CRM_QUERY for ANY question about personal information: name, age, DOB, email, phone, address
- Use CRM_QUERY for account metadata: account numbers, account names, account types, primary account
- Use CRM_QUERY for SERVICE REQUESTS: tickets, complaints, open issues
- Use CRM_QUERY for OFFERS: pre-approved loans/cards, eligibility
- Use CRM_QUERY for FLAGS: VIP status, customer tier, risk profile
- Use CRM_QUERY for INTERACTION HISTORY: "what did we discuss", "last time"
- DO NOT use CRM_QUERY for account balances (use ACCOUNT_QUERY instead)
- DO NOT use CRM_QUERY for transactions (use TRANSACTION_QUERY instead)

Return ONLY a JSON object:
{
    "intent": "ACCOUNT_QUERY|TRANSACTION_QUERY|FINANCIAL_ADVICE|ANALYTICS|CRM_QUERY|GENERAL",
    "confidence": 0.0-1.0,
    "entities": {
        "account_type": "checking|savings|credit|all",
        "time_period": "last_week|last_month|last_3_months|specific_date",
        "amount": "numeric_value",
        "category": "dining|shopping|groceries|etc",
        "loan_type": "mortgage|auto|personal",
        "comparison_type": "month_over_month|year_over_year|historical"
        "profile_field": "name|email|phone|address|dob|age|account_number|account_type|full_profile"
    },
    "reasoning": "Brief explanation of classification"
}

Be precise and consistent in classification."""
        )
    
    def process(self, context: dict, query: str) -> dict:
        """Classify the user's intent with enhanced accuracy"""
        
        # Provide context about user's financial situation for better routing
        has_income = len(context.get("income", [])) > 0
        has_liabilities = len(context.get("liabilities", [])) > 0
        has_spending_data = len(context.get("spending_summary", [])) > 0
        
        context_info = f"""
User Context:
- Has Income Data: {has_income}
- Has Debt Data: {has_liabilities}
- Has Spending History: {has_spending_data}
- Number of Accounts: {len(context.get('accounts', []))}
- Number of Recent Transactions: {len(context.get('recent_transactions', []))}
"""
        
        messages = [
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": f"{context_info}\n\nClassify this query: {query}"}
        ]
        
        response = self.call_llm(messages, temperature=0.2)  # Lower temperature for consistency
        
        if response["type"] == "error":
            return self.format_response(
                "I'm having trouble understanding your question. Could you rephrase it?",
                metadata={
                    "intent": "GENERAL",
                    "confidence": 0.3,
                    "entities": {},
                    "reasoning": "Error in classification, defaulting to GENERAL"
                }
            )
        
        try:
            # Parse JSON response
            content = response["content"].strip()
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()
            
            classification = json.loads(content)
            
            # Validate classification
            valid_intents = ["ACCOUNT_QUERY", "TRANSACTION_QUERY", "FINANCIAL_ADVICE", "ANALYTICS", "CRM_QUERY", "GENERAL"]
            if classification.get("intent") not in valid_intents:
                classification["intent"] = "GENERAL"
                classification["confidence"] = 0.5
                classification["reasoning"] = "Invalid intent detected, defaulting to GENERAL"
            
            return self.format_response(
                content="Intent classified",
                metadata=classification
            )
        except Exception as e:
            print(f"⚠️ Router parsing error: {e}")
            print(f"Response content: {response.get('content', 'No content')}")
            # Default to GENERAL if parsing fails
            return self.format_response(
                content="Intent classified",
                metadata={
                    "intent": "GENERAL",
                    "confidence": 0.5,
                    "entities": {},
                    "reasoning": f"Failed to parse response: {str(e)}"
                }
            )