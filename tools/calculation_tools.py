# tools/calculation_tools.py

class CalculationTools:
    """Enhanced financial calculation utilities"""
    
    @staticmethod
    def calculate_dti_ratio(monthly_debt: float, monthly_income: float) -> float:
        """Calculate Debt-to-Income ratio"""
        if monthly_income == 0:
            return 0
        return (monthly_debt / monthly_income) * 100
    
    @staticmethod
    def calculate_affordability(monthly_payment: float, monthly_income: float, current_obligations: float) -> dict:
        """Check if a payment is affordable"""
        new_total_obligations = current_obligations + monthly_payment
        new_dti = (new_total_obligations / monthly_income * 100) if monthly_income > 0 else 100
        
        return {
            "affordable": new_dti < 43,  # Updated to 43% (standard mortgage threshold)
            "new_dti": round(new_dti, 2),
            "monthly_payment": monthly_payment,
            "disposable_income_after": round(monthly_income - new_total_obligations, 2)
        }
    
    @staticmethod
    def calculate_financial_health_score(dti_ratio: float, credit_util: float, income: float, expenses: float) -> int:
        """Calculate financial health score (0-100)"""
        score = 100
        
        # DTI penalty
        if dti_ratio > 50:
            score -= 40
        elif dti_ratio > 43:
            score -= 30
        elif dti_ratio > 36:
            score -= 15
        
        # Credit utilization penalty
        if credit_util > 70:
            score -= 30
        elif credit_util > 50:
            score -= 20
        elif credit_util > 30:
            score -= 10
        
        # Savings rate calculation
        if income > 0:
            savings_rate = ((income - expenses) / income) * 100
            if savings_rate < 0:
                score -= 20  # Spending more than earning
            elif savings_rate < 10:
                score -= 15
            elif savings_rate > 20:
                score += 10
        
        return max(0, min(100, score))
    
    @staticmethod
    def calculate_mortgage_payment(loan_amount: float, annual_rate: float = 7.0, years: int = 30) -> float:
        """Calculate monthly mortgage payment (Principal + Interest only)"""
        if loan_amount <= 0:
            return 0
        
        monthly_rate = (annual_rate / 100) / 12
        num_payments = years * 12
        
        if monthly_rate == 0:
            return loan_amount / num_payments
        
        payment = loan_amount * (monthly_rate * (1 + monthly_rate)**num_payments) / \
                  ((1 + monthly_rate)**num_payments - 1)
        return round(payment, 2)
    
    @staticmethod
    def calculate_max_home_price(monthly_income: float, current_obligations: float, 
                                 down_payment: float = 0, max_dti: float = 43.0,
                                 annual_rate: float = 7.0, property_tax_rate: float = 1.2,
                                 insurance_rate: float = 0.5) -> dict:
        """Calculate maximum affordable home price"""
        
        # Maximum monthly payment based on DTI
        max_monthly_payment = (monthly_income * (max_dti / 100)) - current_obligations
        
        if max_monthly_payment <= 0:
            return {
                "max_home_price": 0,
                "max_loan_amount": 0,
                "monthly_payment": 0,
                "affordable": False,
                "reason": "Current obligations exceed DTI limit"
            }
        
        # Estimate PITI (Principal, Interest, Tax, Insurance)
        # Assume 80% of payment goes to P&I, 20% to T&I
        max_pi_payment = max_monthly_payment * 0.75  # Conservative estimate
        
        # Calculate max loan using mortgage formula (reverse calculation)
        monthly_rate = (annual_rate / 100) / 12
        num_payments = 30 * 12
        
        if monthly_rate == 0:
            max_loan = max_pi_payment * num_payments
        else:
            max_loan = max_pi_payment * ((1 + monthly_rate)**num_payments - 1) / \
                      (monthly_rate * (1 + monthly_rate)**num_payments)
        
        max_home_price = max_loan + down_payment
        
        # Calculate actual PITI
        pi_payment = CalculationTools.calculate_mortgage_payment(max_loan, annual_rate, 30)
        annual_tax = max_home_price * (property_tax_rate / 100)
        annual_insurance = max_home_price * (insurance_rate / 100)
        monthly_tax = annual_tax / 12
        monthly_insurance = annual_insurance / 12
        
        total_monthly = pi_payment + monthly_tax + monthly_insurance
        
        return {
            "max_home_price": round(max_home_price, 2),
            "max_loan_amount": round(max_loan, 2),
            "down_payment": round(down_payment, 2),
            "monthly_payment": round(total_monthly, 2),
            "monthly_pi": round(pi_payment, 2),
            "monthly_tax": round(monthly_tax, 2),
            "monthly_insurance": round(monthly_insurance, 2),
            "affordable": True,
            "new_dti": round(((current_obligations + total_monthly) / monthly_income * 100), 2)
        }
    
    @staticmethod
    def calculate_auto_loan_payment(loan_amount: float, annual_rate: float = 6.5, years: int = 5) -> float:
        """Calculate monthly auto loan payment"""
        if loan_amount <= 0:
            return 0
        
        monthly_rate = (annual_rate / 100) / 12
        num_payments = years * 12
        
        if monthly_rate == 0:
            return loan_amount / num_payments
        
        payment = loan_amount * (monthly_rate * (1 + monthly_rate)**num_payments) / \
                  ((1 + monthly_rate)**num_payments - 1)
        return round(payment, 2)
    
    @staticmethod
    def calculate_max_auto_loan(monthly_income: float, current_obligations: float,
                               down_payment: float = 0, max_dti: float = 43.0,
                               annual_rate: float = 6.5, years: int = 5) -> dict:
        """Calculate maximum affordable auto loan"""
        
        max_monthly_payment = (monthly_income * (max_dti / 100)) - current_obligations
        
        if max_monthly_payment <= 0:
            return {
                "max_auto_price": 0,
                "max_loan_amount": 0,
                "monthly_payment": 0,
                "affordable": False,
                "reason": "Current obligations exceed DTI limit"
            }
        
        # Calculate max loan using auto loan formula
        monthly_rate = (annual_rate / 100) / 12
        num_payments = years * 12
        
        if monthly_rate == 0:
            max_loan = max_monthly_payment * num_payments
        else:
            max_loan = max_monthly_payment * ((1 + monthly_rate)**num_payments - 1) / \
                      (monthly_rate * (1 + monthly_rate)**num_payments)
        
        max_auto_price = max_loan + down_payment
        actual_payment = CalculationTools.calculate_auto_loan_payment(max_loan, annual_rate, years)
        
        return {
            "max_auto_price": round(max_auto_price, 2),
            "max_loan_amount": round(max_loan, 2),
            "down_payment": round(down_payment, 2),
            "monthly_payment": round(actual_payment, 2),
            "loan_term_years": years,
            "interest_rate": annual_rate,
            "affordable": True,
            "new_dti": round(((current_obligations + actual_payment) / monthly_income * 100), 2)
        }
    
    @staticmethod
    def get_dti_assessment(dti_ratio: float) -> dict:
        """Get DTI assessment and recommendations"""
        if dti_ratio < 20:
            return {
                "rating": "Excellent",
                "description": "Your debt level is very manageable and well below recommended limits.",
                "impact": "You should have no issues qualifying for new credit.",
                "color": "green"
            }
        elif dti_ratio < 36:
            return {
                "rating": "Good",
                "description": "Your debt level is within healthy limits.",
                "impact": "You should qualify for most loans with favorable terms.",
                "color": "green"
            }
        elif dti_ratio < 43:
            return {
                "rating": "Fair",
                "description": "Your debt level is approaching the upper limit.",
                "impact": "You may qualify for loans, but options might be limited.",
                "color": "yellow"
            }
        elif dti_ratio < 50:
            return {
                "rating": "High",
                "description": "Your debt level is concerning and above most lending thresholds.",
                "impact": "Loan approval will be difficult. Consider reducing debt before applying.",
                "color": "orange"
            }
        else:
            return {
                "rating": "Critical",
                "description": "Your debt level is very high and poses significant financial risk.",
                "impact": "Immediate action needed. New loan approval is highly unlikely.",
                "color": "red"
            }
    
    @staticmethod
    def get_credit_utilization_assessment(util_ratio: float) -> dict:
        """Get credit utilization assessment"""
        if util_ratio < 10:
            return {
                "rating": "Excellent",
                "description": "Your credit utilization is very low.",
                "impact": "This is ideal and positively impacts your credit score.",
                "color": "green"
            }
        elif util_ratio < 30:
            return {
                "rating": "Good",
                "description": "Your credit utilization is within the recommended range.",
                "impact": "This is healthy and should maintain a good credit score.",
                "color": "green"
            }
        elif util_ratio < 50:
            return {
                "rating": "Fair",
                "description": "Your credit utilization is higher than recommended.",
                "impact": "Consider paying down balances to improve your credit score.",
                "color": "yellow"
            }
        elif util_ratio < 75:
            return {
                "rating": "High",
                "description": "Your credit utilization is quite high.",
                "impact": "This is likely hurting your credit score. Prioritize paying down balances.",
                "color": "orange"
            }
        else:
            return {
                "rating": "Critical",
                "description": "Your credit utilization is dangerously high.",
                "impact": "This is significantly damaging your credit score. Immediate action needed.",
                "color": "red"
            }
    
    @staticmethod
    def suggest_improvements(metrics: dict, target_dti: float = 36.0) -> list:
        """Generate actionable improvement suggestions"""
        suggestions = []
        
        dti_ratio = metrics.get('dti_ratio', 0)
        credit_util = metrics.get('credit_utilization', 0)
        monthly_income = metrics.get('monthly_income', 0)
        monthly_obligations = metrics.get('monthly_obligations', 0)
        
        # DTI improvements
        if dti_ratio > target_dti and monthly_income > 0:
            target_obligations = monthly_income * (target_dti / 100)
            needed_reduction = monthly_obligations - target_obligations
            
            if needed_reduction > 0:
                suggestions.append({
                    "category": "Debt-to-Income Ratio",
                    "priority": "High",
                    "current": f"{dti_ratio:.1f}%",
                    "target": f"{target_dti:.1f}%",
                    "action": f"Reduce monthly debt payments by ${needed_reduction:.0f}",
                    "impact": "This will bring your DTI to the target range and significantly improve loan eligibility."
                })
        
        # Credit utilization improvements
        if credit_util > 30:
            suggestions.append({
                "category": "Credit Utilization",
                "priority": "High" if credit_util > 50 else "Medium",
                "current": f"{credit_util:.1f}%",
                "target": "Below 30%",
                "action": "Pay down credit card balances to below 30% of total limits",
                "impact": "This will improve your credit score and loan approval chances."
            })
        
        # Income improvements
        if monthly_income > 0 and dti_ratio > 36:
            needed_income = monthly_obligations / (target_dti / 100)
            income_increase = needed_income - monthly_income
            
            if income_increase > 0:
                suggestions.append({
                    "category": "Income",
                    "priority": "Medium",
                    "current": f"${monthly_income:,.0f}/month",
                    "target": f"${needed_income:,.0f}/month",
                    "action": f"Increase monthly income by ${income_increase:.0f} (through raises, side income, etc.)",
                    "impact": "Higher income improves your debt-to-income ratio without reducing debt."
                })
        
        # Savings rate
        if 'avg_monthly_expenses' in metrics:
            expenses = metrics['avg_monthly_expenses']
            if monthly_income > 0:
                savings_rate = ((monthly_income - monthly_obligations - expenses) / monthly_income) * 100
                
                if savings_rate < 10:
                    suggestions.append({
                        "category": "Savings Rate",
                        "priority": "Medium",
                        "current": f"{savings_rate:.1f}%",
                        "target": "At least 10-15%",
                        "action": "Reduce discretionary spending to save at least 10% of income",
                        "impact": "Building emergency savings prevents future debt and improves financial stability."
                    })
        
        return suggestions
    
    @staticmethod
    def calculate_payoff_scenario(balance: float, monthly_payment: float, annual_rate: float) -> dict:
        """Calculate how long it takes to pay off a debt"""
        if monthly_payment <= 0 or balance <= 0:
            return {"error": "Invalid inputs"}
        
        monthly_rate = (annual_rate / 100) / 12
        
        # Check if payment covers interest
        monthly_interest = balance * monthly_rate
        if monthly_payment <= monthly_interest:
            return {
                "payoff_months": float('inf'),
                "total_paid": float('inf'),
                "total_interest": float('inf'),
                "warning": "Payment doesn't cover monthly interest. Debt will never be paid off."
            }
        
        # Calculate payoff time
        months = -(1/12) * (1/monthly_rate) * (balance * monthly_rate / monthly_payment - 1)
        months = round(months * 12)
        
        total_paid = monthly_payment * months
        total_interest = total_paid - balance
        
        return {
            "payoff_months": months,
            "payoff_years": round(months / 12, 1),
            "total_paid": round(total_paid, 2),
            "total_interest": round(total_interest, 2),
            "interest_percentage": round((total_interest / balance) * 100, 1)
        }