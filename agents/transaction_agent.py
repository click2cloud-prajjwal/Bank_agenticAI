# agents/transaction_agent.py
from agents.base_agent import BaseAgent
from collections import defaultdict
import json

class TransactionAgent(BaseAgent):
    """Handles transaction queries with voice-optimized responses"""
    
    def __init__(self):
        super().__init__(
            name="Transaction Analyst",
            role="Transaction & Spending Expert",
            instructions="""You are a transaction analyst for a VOICE-based banking assistant.

Keep responses BRIEF and CONVERSATIONAL.

RESPONSE RULES:
1. Start with the key finding (1 sentence)
2. Give 2-3 supporting details
3. Max 50 words for simple queries
4. Sound natural and friendly
5. After answering, end with "What else can I help you with?" - NO additional follow-up questions

EXAMPLES:

User: "Show me my recent transactions"
Response: "Your last five transactions are: $85 at Whole Foods yesterday, $45 at Shell on Tuesday, $120 at Amazon last Friday, $15 at Starbucks, and a $2,500 paycheck deposit last Monday. Anything else?"

User: "What did I spend on groceries?"
Response: "You've spent $340 on groceries this month across 8 trips. That's about $85 per week, which is up from your usual $65 weekly average. What else can I help you with?"

User: "Where's my money going?"
Response: "Your top spending categories are dining at $420, groceries at $340, and shopping at $280. Dining is your biggest expense and it's up 30% from last month. Do you have any other questions?"

User: "Do I have any large charges?"
Response: "Yes, there's an $850 charge to ABC Furniture on November 20th. That's your largest purchase this month. Everything else is under $200. Anything else?"

User: "Show me my Amazon purchases"
Response: "You have 4 Amazon transactions this month totaling $285: $120 on the 15th, $85 on the 10th, $55 on the 5th, and $25 on the 2nd. What else would you like to know?"

User: "Any unusual spending?"
Response: "Yes, I see a $500 charge from XYZ Online Store on the 23rd, which is much higher than your typical purchases. If you don't recognize it, you may want to review it. Anything else?"

CRITICAL RULES:
- Keep it short, clear, and conversational
- After providing transaction details, ALWAYS end with "What else can I help you with?" or "Anything else?" or "Do you have any other questions?"
- DO NOT ask follow-up questions like "Would you like to see more transactions?" or "Should I analyze your spending?"
- DO NOT offer additional analysis unprompted
- Just answer their question, then ask if they need anything else
- Maximum 50-60 words per response"""
        )
    
    def process(self, context: dict, query: str, conversation_history: list = None) -> dict:
        """Process transaction queries with short responses"""
        
        transactions = context.get("recent_transactions", [])
        spending = context.get("spending_summary", [])
        
        if not transactions:
            return self.format_response(
                "I don't see any recent transactions yet. They might still be syncing from your bank.",
                metadata={"error": "no_transactions"}
            )
        
        total_spent = sum(t['amount'] for t in transactions if t['amount'] > 0)
        total_income = sum(abs(t['amount']) for t in transactions if t['amount'] < 0)
        
        # Category analysis
        by_category = defaultdict(lambda: {'amount': 0, 'count': 0})
        for t in transactions:
            if t['amount'] > 0:
                category = t.get('category', 'Uncategorized')
                by_category[category]['amount'] += t['amount']
                by_category[category]['count'] += 1
        
        top_categories = sorted(by_category.items(), key=lambda x: x[1]['amount'], reverse=True)[:3]
        
        # Find unusual large transactions
        if transactions:
            avg_transaction = sum(abs(t['amount']) for t in transactions) / len(transactions)
            unusual = [t for t in transactions if t['amount'] > 0 and t['amount'] > (avg_transaction * 2)]
            unusual = sorted(unusual, key=lambda x: x['amount'], reverse=True)[:2]
        else:
            unusual = []
        
        # MoM comparison
        mom_change = None
        if len(spending) >= 2:
            latest = spending[0]
            previous = spending[1]
            expense_change = latest['expenses'] - previous['expenses']
            expense_pct = (expense_change / previous['expenses'] * 100) if previous['expenses'] > 0 else 0
            mom_change = {
                'current': latest['expenses'],
                'previous': previous['expenses'],
                'change_pct': expense_pct
            }
        
        # Check if user wants details
        query_lower = query.lower()
        wants_details = any(word in query_lower for word in [
            'why', 'explain', 'detail', 'breakdown', 'more', 'tell me more'
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

TRANSACTION DATA:
Total Spent (last 30 days): ${total_spent:,.0f}
Total Income: ${total_income:,.0f}
Transaction Count: {len(transactions)}

Top 3 Categories:
{json.dumps([{'category': cat, 'amount': f"${data['amount']:.0f}", 'count': data['count']} for cat, data in top_categories], indent=2)}

Recent Transactions (last 5):
{json.dumps(transactions[:5], indent=2)}

{"Large/Unusual Transactions: " + json.dumps(unusual, indent=2) if unusual else "No unusual transactions"}

{"Month Change: Up " + str(abs(mom_change['change_pct'])) + "%" if mom_change and mom_change['change_pct'] > 5 else ""}

CUSTOMER QUESTION: {query}

{"Provide 2-3 detailed points (max 60 words)" if wants_details else "Give a BRIEF answer (1-2 sentences, max 40 words)"} Sound natural."""
        
        messages = [
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": data_summary}
        ]
        
        response = self.call_llm(messages, temperature=0.6)
        
        if response["type"] == "error":
            return self.format_response(
                "I'm having trouble pulling up your transactions. Try again in a moment.",
                metadata={"error": "llm_error"}
            )
        
        return self.format_response(
            content=response["content"],
            metadata={
                "transactions_analyzed": len(transactions),
                "total_spent": round(total_spent, 2),
                "categories": len(by_category)
            }
        )