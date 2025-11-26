# agents/financial_advisor_agent.py
from agents.base_agent import BaseAgent
from tools.calculation_tools import CalculationTools
import json

class FinancialAdvisorAgent(BaseAgent):
    """Provides financial advice optimized for voice/conversational interactions"""
    
    def __init__(self):
        super().__init__(
            name="Financial Advisor",
            role="Financial Planning & Eligibility Expert",
            instructions="""You are a financial advisor for a voice-based banking assistant. Your responses must be SHORT and CONVERSATIONAL like a real phone conversation.

CRITICAL RULES FOR VOICE INTERACTIONS:
1. Give the ANSWER FIRST in 1-2 sentences
2. Then ask: "Would you like me to explain the details?"
3. Keep initial response under 50 words
4. No bullet points, no long paragraphs
5. Sound like a human banker on a phone call

TWO-STEP RESPONSE FORMAT:

Step 1 - Initial Response (if user asks a new question):
- Give YES/NO answer with ONE key reason
- Max 2 sentences (under 50 words)
- Ask: "Would you like me to explain the details?"

Step 2 - Detailed Response (ONLY if user says yes/more/why/details):
- Provide 3-4 key points explaining the situation
- Keep each point to one sentence
- Stay under 100 words total
- END WITH: "Do you have any other questions?" or "What else can I help you with?"
- DO NOT ask follow-up questions about their situation
- DO NOT offer additional services unless asked

CRITICAL: After giving detailed explanation, ALWAYS end with "Do you have any other questions?" or similar. NEVER ask additional follow-up questions like "Would you like advice on..." or "Should I explain...". Just wrap up and ask if they need anything else.

EXAMPLES:

User: "Can I afford a $25,000 car?"

Step 1 Response:
"No, you can't afford a $25,000 car right now because your monthly income is zero, so you can't cover any loan payments. Would you like me to explain the details?"

[If user says yes/more/why/tell me/sure]

Step 2 Response:
"Since your monthly income is zero, you have no steady cash flow to cover car loan payments. Even though you have $12,380 in liquid assets, lenders focus on your ability to repay monthly. Without income, your debt-to-income ratio isn't applicable but essentially means you can't support new debt. Do you have any other questions?"

---

User: "Can I get a $350,000 house with $50,000 down?"

Step 1 Response:
"Based on your current income and debts, you cannot afford that home. Your debt-to-income ratio would be 51%, which is above the 43% limit lenders require. Would you like me to explain the details?"

[If user says yes/sure/tell me]

Step 2 Response:
"Here's the breakdown: Your monthly income is $6,000, but you're already paying $1,200 in existing debt. The mortgage would add $1,900 per month, pushing your DTI to 51%. Lenders typically require DTI under 43%. You'd need to either pay down about $8,000 in debt or look at homes around $280,000 instead. What else can I help you with?"

---

User: "Why was my loan denied?"

Step 1 Response:
"Your loan was likely denied because your debt-to-income ratio is 48%, which exceeds the standard 43% threshold. Would you like me to explain the details?"

[If user says yes]

Step 2 Response:
"Your DTI is 48% because you're paying $2,880 in monthly debts on a $6,000 income. Lenders want this below 43%. To qualify, you'd need to reduce monthly debt by about $300. You could pay down a credit card or personal loan to achieve this. Do you have any other questions?"

---

TONE:
- Conversational and warm
- Direct and honest
- Sound like a human, not a robot
- Empathetic but factual
- No pushy sales talk

REMEMBER: 
- Step 1: Short answer + ask if they want details
- Step 2: Explain in 3-4 points + END with "Do you have any other questions?"
- NEVER ask additional follow-up questions after giving detailed explanation
- Keep it conversational like a real phone call."""
        )
        self.calc_tools = CalculationTools()
    
    def process(self, context: dict, query: str, conversation_history: list = None) -> dict:
        """Process financial advice with voice-optimized responses"""
        
        metrics = context.get("metrics", {})
        income = context.get("income", [])
        liabilities = context.get("liabilities", [])
        spending = context.get("spending_summary", [])
        accounts = context.get("accounts", [])
        
        # Calculate key metrics
        monthly_income = metrics.get("monthly_income", 0)
        monthly_obligations = metrics.get("monthly_obligations", 0)
        dti_ratio = metrics.get("dti_ratio", 0)
        credit_utilization = metrics.get("credit_utilization", 0)
        
        # Calculate average monthly expenses
        avg_monthly_expenses = 0
        if spending:
            recent_expenses = [s['expenses'] for s in spending[:3]]
            avg_monthly_expenses = sum(recent_expenses) / len(recent_expenses) if recent_expenses else 0
        
        disposable_income = monthly_income - monthly_obligations - avg_monthly_expenses
        
        # Financial health assessment
        health_score = self.calc_tools.calculate_financial_health_score(
            dti_ratio, credit_utilization, monthly_income, avg_monthly_expenses
        )
        
        dti_assessment = self.calc_tools.get_dti_assessment(dti_ratio)
        credit_assessment = self.calc_tools.get_credit_utilization_assessment(credit_utilization)
        
        total_liquid_assets = sum(a.get('balance', 0) for a in accounts if a.get('type') in ['depository'])
        
        # Mortgage calculation
        mortgage_calc = self.calc_tools.calculate_max_home_price(
            monthly_income, monthly_obligations,
            down_payment=total_liquid_assets * 0.2,
            max_dti=43.0
        )
        
        # Auto loan calculation
        auto_calc = self.calc_tools.calculate_max_auto_loan(
            monthly_income, monthly_obligations,
            down_payment=min(total_liquid_assets * 0.1, 5000),
            max_dti=43.0
        )
        
        suggestions = self.calc_tools.suggest_improvements(
            {**metrics, 'avg_monthly_expenses': avg_monthly_expenses}
        )
        
        savings_rate = 0
        if monthly_income > 0:
            monthly_savings = monthly_income - monthly_obligations - avg_monthly_expenses
            savings_rate = (monthly_savings / monthly_income) * 100
        
        # Check if this is a follow-up request for details
        is_followup = False
        if conversation_history:
            last_exchange = conversation_history[-1]
            if last_exchange.get('agent_used') == self.name:
                query_lower = query.lower()
                is_followup = any(word in query_lower for word in [
                    'yes', 'yeah', 'yep', 'sure', 'ok', 'okay',
                    'why', 'how', 'explain', 'details', 'more', 
                    'tell me', 'go ahead', 'breakdown', 'elaborate'
                ])
        
        # Build conversation context
        conversation_context = ""
        if conversation_history:
            recent = conversation_history[-2:]
            conversation_context = "RECENT CONVERSATION:\n"
            for exchange in recent:
                conversation_context += f"User: {exchange['user_query']}\n"
                conversation_context += f"Assistant: {exchange['bot_response'][:150]}...\n"
            conversation_context += "\n"
        
        data_summary = f"""
{conversation_context}

FINANCIAL PROFILE SUMMARY:
Monthly Income: ${monthly_income:,.0f}
Monthly Debt Payments: ${monthly_obligations:,.0f}
Average Monthly Expenses: ${avg_monthly_expenses:,.0f}
Disposable Income: ${disposable_income:,.0f}

DTI Ratio: {dti_ratio:.1f}% (Target: <43%)
Credit Utilization: {credit_utilization:.1f}% (Target: <30%)
Financial Health Score: {health_score}/100

Liquid Assets: ${total_liquid_assets:,.0f}
Savings Rate: {savings_rate:.1f}%

Max Affordable Home: ${mortgage_calc.get('max_home_price', 0):,.0f}
Max Affordable Auto: ${auto_calc.get('max_auto_price', 0):,.0f}

Debt Details: {json.dumps(liabilities, indent=2) if liabilities else "No debts"}

RESPONSE STYLE REQUIRED:
{"DETAILED - User asked for more information" if is_followup else "BRIEF - Give short answer + ask if they want details"}

CUSTOMER QUESTION: {query}

{"Provide a detailed 3-4 point explanation (max 100 words)" if is_followup else "Give a 2-sentence answer with ONE key metric, then ask: 'Would you like me to explain the details?'"}
"""
        
        messages = [
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": data_summary}
        ]
        
        response = self.call_llm(messages, temperature=0.7)
        
        if response["type"] == "error":
            return self.format_response(
                "I'm having trouble accessing your financial data right now. Could you try again?",
                metadata={"error": "llm_error"}
            )
        
        return self.format_response(
            content=response["content"],
            metadata={
                "dti_ratio": round(dti_ratio, 2),
                "dti_rating": dti_assessment['rating'],
                "credit_utilization": round(credit_utilization, 2),
                "health_score": health_score,
                "disposable_income": round(disposable_income, 2),
                "max_home_price": mortgage_calc.get('max_home_price', 0),
                "max_auto_price": auto_calc.get('max_auto_price', 0),
                "is_followup": is_followup
            }
        )