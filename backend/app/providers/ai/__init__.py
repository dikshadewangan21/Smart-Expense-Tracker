from typing import Protocol
from app.core.config import get_settings
from app.core.money import fmt_money

class AIProvider(Protocol):
    def reply(self, prompt: str, context_summary: dict, history: list[dict]) -> str:
        ...

class DeterministicMoneyCoachProvider:
    """Intelligent rule-based & deterministic coach that analyzes computed figures without requiring external API keys."""

    def reply(self, prompt: str, context_summary: dict, history: list[dict]) -> str:
        low = prompt.lower()
        cur = context_summary.get("currency", "INR")
        health = context_summary.get("health", {})
        budget = context_summary.get("budget", {})
        savings = context_summary.get("savings", {})
        bills = context_summary.get("bills", {})
        debts = context_summary.get("debts", {})
        goals = context_summary.get("goals", {})
        insights = context_summary.get("insights", [])

        # Categorize intent and provide grounded, mathematically exact explanations
        if any(w in low for w in ["health", "score"]):
            score = health.get("score")
            comps = health.get("components", [])
            lines = [f"Your overall Financial Health Score is **{score}/100**." if score is not None else "Your health score will be computed once more transactions are recorded."]
            for c in comps:
                lines.append(f"- **{c.get('label')}**: {c.get('points')}/{c.get('max')} pts ({c.get('reason')})")
            return "\n\n".join(lines)

        if any(w in low for w in ["budget", "spend", "limit"]):
            if not budget:
                return "You don't have a budget set up for this month yet. Head over to Budgets to set spending limits by category."
            total_limit = budget.get("total_limit", 0)
            total_used = budget.get("total_used", 0)
            rem = budget.get("remaining", 0)
            used_pct = round(total_used / total_limit * 100, 1) if total_limit else 0
            lines = [
                f"You have used **{used_pct}%** of your monthly budget ({fmt_money(total_used, cur)} spent out of {fmt_money(total_limit, cur)}).",
                f"You have **{fmt_money(rem, cur)}** remaining for the rest of the month." if rem >= 0 else f"You have exceeded your total limit by **{fmt_money(abs(rem), cur)}**."
            ]
            over = [c for c in budget.get("categories", []) if c.get("percent_used") and c.get("percent_used") > 100]
            if over:
                cat_names = ", ".join(c.get("category") for c in over)
                lines.append(f"⚠️ Categories over budget: **{cat_names}**.")
            return "\n\n".join(lines)

        if any(w in low for w in ["saving", "save"]):
            rate = savings.get("savings_rate")
            inc = savings.get("income", 0)
            exp = savings.get("expenses", 0)
            net = inc - exp
            if rate is not None:
                advice = "Great job! A 20%+ savings rate is healthy." if rate >= 20 else "To build resilience, try trimming discretionary categories to aim for at least a 20% savings rate."
                return f"This month you have saved **{fmt_money(net, cur)}** out of **{fmt_money(inc, cur)}** income, giving a savings rate of **{rate}%**.\n\n{advice}"
            return "No income recorded for this period to calculate a savings rate."

        if any(w in low for w in ["bill", "due"]):
            overdue = bills.get("overdue_count", 0)
            upcoming_total = bills.get("due_next_7_days_total", 0)
            monthly = bills.get("monthly_commitment", 0)
            lines = [f"Your monthly commitments for bills and recurring charges are about **{fmt_money(monthly, cur)}/month**."]
            if overdue > 0:
                lines.append(f"🚨 You have **{overdue} overdue bill(s)** amounting to {fmt_money(bills.get('overdue_total', 0), cur)}. Please check the Bills page!")
            else:
                lines.append(f"You have **{fmt_money(upcoming_total, cur)}** due in the next 7 days.")
            return "\n\n".join(lines)

        if any(w in low for w in ["debt", "loan", "emi"]):
            owed = debts.get("total_owed", 0)
            emi = debts.get("monthly_emi", 0)
            if owed > 0:
                return f"You currently owe **{fmt_money(owed, cur)}** across your loans/cards, with monthly EMI commitments of **{fmt_money(emi, cur)}**."
            return "You have no active debts recorded. All clear!"

        if any(w in low for w in ["goal", "target"]):
            items = goals.get("items", [])
            if not items:
                return "You have no savings goals set up yet. Set a goal (e.g. Emergency Fund or Travel) in the Goals page to track progress."
            lines = [f"You are tracking **{len(items)}** savings goal(s):"]
            for g in items[:4]:
                lines.append(f"- **{g.get('name')}**: {fmt_money(g.get('current_amount', 0), cur)} / {fmt_money(g.get('target_amount', 0), cur)} ({g.get('percent', 0)}%)")
            return "\n\n".join(lines)

        # General summary / fallback
        resp = [
            f"Here is your financial snapshot for {context_summary.get('period_label', 'this month')}:",
            f"- **Net Balance**: {fmt_money(context_summary.get('total_balance', 0), cur)}",
            f"- **Spending**: {fmt_money(savings.get('expenses', 0), cur)}",
            f"- **Income**: {fmt_money(savings.get('income', 0), cur)}",
        ]
        if insights:
            resp.append("\n**Key Observation**:\n" + "\n".join(f"- {i}" for i in insights[:2]))
        resp.append("\nAsk me anything specific about your budget, savings rate, bills due, or financial health!")
        return "\n".join(resp)

def get_ai_provider() -> AIProvider:
    # Here we default to the deterministic provider if no external key is supplied
    return DeterministicMoneyCoachProvider()
