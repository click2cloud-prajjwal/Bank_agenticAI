# agents/analytics_agent.py
from agents.base_agent import BaseAgent
import json
from collections import defaultdict
from tools.user_profile_tools import UserProfileTools

class AnalyticsAgent(BaseAgent):
    """Generates insights with voice-optimized short responses"""
    
    def __init__(self):
        super().__init__(
            name="Analytics Specialist",
            role="Data Analysis & Insights Expert",
            instructions="""You are a financial analytics expert for a VOICE-based banking assistant.

Keep responses SHORT and INSIGHTFUL.

PERSONALIZATION:
- Use the customer's first name occasionally for warmth
- Consider their age for age-appropriate financial advice
- Reference their location for regional context if relevant
- Tailor recommendations based on their life stage

RESPONSE RULES:
1. Start with the KEY INSIGHT (1 sentence)
2. Give 2-3 supporting facts
3. Max 60 words total
4. Sound conversational

ENDING RULE:
- If your response already ends with a follow-up question 
  (e.g., "Would you like details?", "Do you want more info?"), 
  DO NOT add "What else can I help you with?".
- Use ONLY ONE question per response.
- If no follow-up question is needed, then end with 
  "What else can I help you with?".

EXAMPLES:

User: "How's my spending trending?"
Response: "Your spending is up 28% this month to $4,200. The main drivers are dining up $290 and shopping up $170. If this continues, you'll spend about $5,000 next month. What else can I help you with?"

User: "Compare this month to last"
Response: "This month you spent $4,200 versus $3,280 last month. That's $920 more, mainly from increased dining and shopping. Your income stayed the same at $7,000. Anything else you'd like to know?"

User: "Where should I cut back?"
Response: "Your dining spending is $742 per month, which is 15% of your income. That's at the upper recommended limit. Reducing to $500 would save you $240 monthly or $2,900 per year. What else can I help you with?"

User: "Am I saving enough?"
Response: "You're saving about 8% of your income right now. The recommended rate is 15-20%. To hit 15%, you'd need to save an extra $350 per month. Do you have any other questions?"

User: "Why did my spending go up?"
Response: "Your spending jumped 35% because of three large purchases: $850 furniture, $420 electronics, and increased dining from $300 to $520. These are mostly one-time expenses. Anything else?"

CRITICAL RULES:
- Keep it brief, actionable, and conversational
- After giving insights, ALWAYS end with "What else can I help you with?" or "Do you have any other questions?" or "Anything else?"
- DO NOT ask follow-up analytical questions like "Would you like me to analyze..." or "Should I break down..."
- DO NOT offer additional services unprompted
- Just answer, then ask if they need anything else
- Maximum 60-70 words per response"""
        )
        self.profile_tools = UserProfileTools()
        
    def process(self, context: dict, query: str, conversation_history: list = None) -> dict:
        """Process analytics with short, actionable insights"""
        
        #Get user profile
        profile = context.get("profile", {})
        user_name = profile.get('full_name', '')
        first_name = user_name.split()[0] if user_name else ''
        age = profile.get('age')
        email = profile.get('email')
        address = profile.get('address', {})
        city = address.get('city', '') if address else ''
        state = address.get('state', '') if address else ''

        spending = context.get("spending_summary", [])
        transactions = context.get("recent_transactions", [])
        metrics = context.get("metrics", {})
        
        # Calculate trends
        mom_analysis = []
        if len(spending) >= 2:
            for i in range(min(2, len(spending) - 1)):
                current = spending[i]
                previous = spending[i + 1]
                
                expense_change = current['expenses'] - previous['expenses']
                expense_pct = (expense_change / previous['expenses'] * 100) if previous['expenses'] > 0 else 0
                
                mom_analysis.append({
                    'current_expenses': current['expenses'],
                    'previous_expenses': previous['expenses'],
                    'change': expense_change,
                    'change_pct': expense_pct
                })
        
        # Category analysis
        category_analysis = defaultdict(lambda: {'amount': 0, 'count': 0})
        for txn in transactions:
            if txn['amount'] > 0:
                cat = txn.get('category', 'Uncategorized')
                category_analysis[cat]['amount'] += txn['amount']
                category_analysis[cat]['count'] += 1
        
        total_spending = sum(cat['amount'] for cat in category_analysis.values())
        top_categories = sorted(
            [(cat, data) for cat, data in category_analysis.items()],
            key=lambda x: x[1]['amount'],
            reverse=True
        )[:3]
        
        # Savings rate
        monthly_income = metrics.get('monthly_income', 0)
        monthly_obligations = metrics.get('monthly_obligations', 0)
        latest_expenses = spending[0]['expenses'] if spending else 0
        
        monthly_savings = monthly_income - monthly_obligations - latest_expenses
        savings_rate = (monthly_savings / monthly_income * 100) if monthly_income > 0 else 0
        
        #Age-based insights
        age_context = ""
        if age:
            if age < 30:
                age_context = "At your age, building emergency savings and paying off high-interest debt should be priorities."
            elif 30 <= age < 45:
                age_context = "Given your life stage, balancing savings, investments, and debt management is key."
            elif 45 <= age < 60:
                age_context = "At this point, maximizing retirement contributions and reducing debt is important."
            else:
                age_context = "Focus on preserving wealth and planning for retirement income needs."

        # Check if wants details
        query_lower = query.lower()
        wants_details = any(word in query_lower for word in [
            'why', 'explain', 'detail', 'how', 'what can', 'more'
        ])
        
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
Location: {city}, {state}
Age-Based Context: {age_context}

ANALYTICS SUMMARY:
Monthly Income: ${monthly_income:,.0f}
Current Month Expenses: ${latest_expenses:,.0f}
Monthly Savings: ${monthly_savings:,.0f}
Savings Rate: {savings_rate:.1f}%

Month-over-Month Trend:
{json.dumps(mom_analysis[0], indent=2) if mom_analysis else "No trend data"}

Top 3 Spending Categories:
{json.dumps([{
    'category': cat,
    'amount': f"${data['amount']:.0f}",
    'percentage': f"{(data['amount']/total_spending*100):.0f}%"
} for cat, data in top_categories], indent=2)}

CUSTOMER QUESTION: {query}

{"Provide 2-3 specific insights with numbers (max 60 words)" if wants_details else "Give ONE key insight with ONE supporting fact (max 40 words)"}. Use their first name "{first_name}" naturally if appropriate. Consider their age ({age}) for relevant advice. Be conversational."""
        
        messages = [
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": data_summary}
        ]
        
        response = self.call_llm(messages, temperature=0.6)
        
        if response["type"] == "error":
            return self.format_response(
                 f"{'Hi ' + first_name + '! ' if first_name else ''}I can't generate analytics right now. Try again in a moment.",
                metadata={"error": "llm_error"}
            )
        
        return self.format_response(
            content=response["content"],
            metadata={
                "months_analyzed": len(spending),
                "savings_rate": round(savings_rate, 1),
                "categories_analyzed": len(top_categories),
                "user_name": user_name,
                "user_age": age,
                "age_context_provided": bool(age_context)
            }
        )