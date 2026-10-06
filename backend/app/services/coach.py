from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import AIConversation, AIMessage, User
from app.providers.ai import get_ai_provider
from app.services.dashboard import build_dashboard

def get_or_create_conversation(db: Session, user: User, conversation_id: int | None = None, title: str | None = None) -> AIConversation:
    if conversation_id:
        conv = db.scalar(select(AIConversation).where(AIConversation.id == conversation_id, AIConversation.user_id == user.id))
        if conv:
            return conv
    conv = AIConversation(user_id=user.id, title=title or "Financial Chat")
    db.add(conv)
    db.commit()
    return conv

def ask_coach(db: Session, user: User, prompt: str, today: date, conversation_id: int | None = None) -> dict:
    conv = get_or_create_conversation(db, user, conversation_id, title=prompt[:40])

    # Record user question
    user_msg = AIMessage(conversation_id=conv.id, role="user", content=prompt)
    db.add(user_msg)
    db.flush()

    # Build deterministic context from actual financial services
    dash = build_dashboard(db, user, today)
    context_summary = {
        "currency": user.currency,
        "period_label": today.strftime("%B %Y"),
        "total_balance": float(dash["cards"]["total_balance"]),
        "health": dash["financial_health"],
        "budget": {
            "total_limit": float(dash["budget_status"]["total_limit"]) if dash["budget_status"] else None,
            "total_used": float(dash["budget_status"]["total_used"]) if dash["budget_status"] else None,
            "remaining": float(dash["budget_status"]["remaining"]) if dash["budget_status"] else None,
            "categories": [{
                "category": c["category"],
                "limit": float(c["limit"]),
                "used": float(c["used"]),
                "percent_used": c["percent_used"]
            } for c in (dash["budget_status"]["categories"] if dash["budget_status"] else [])]
        } if dash["budget_status"] else None,
        "savings": {
            "income": float(dash["cards"]["month_income"]),
            "expenses": float(dash["cards"]["month_expenses"]),
            "savings_rate": dash["analytics_summary"]["savings_rate"],
        },
        "bills": dash["upcoming_payments"].get("summary", {}) if isinstance(dash["upcoming_payments"], dict) else {},
        "debts": {
            "total_owed": float(dash["net_worth_detail"]["liabilities"]),
            "monthly_emi": 0,
        },
        "goals": {
            "items": dash["goals"],
        },
        "insights": dash.get("insights", []),
    }

    # Fetch recent conversation history
    history_rows = db.scalars(select(AIMessage).where(AIMessage.conversation_id == conv.id).order_by(AIMessage.id.desc()).limit(6)).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(history_rows)]

    # Generate grounded reply
    provider = get_ai_provider()
    reply_text = provider.reply(prompt, context_summary, history)

    # Save assistant message
    asst_msg = AIMessage(
        conversation_id=conv.id,
        role="assistant",
        content=reply_text,
        source_data={
            "score": dash["financial_health"].get("score"),
            "savings_rate": dash["analytics_summary"].get("savings_rate"),
            "spending": float(dash["cards"]["month_expenses"]),
        }
    )
    db.add(asst_msg)
    db.commit()

    return {
        "conversation_id": conv.id,
        "message": {
            "id": asst_msg.id,
            "role": "assistant",
            "content": reply_text,
            "created_at": asst_msg.created_at,
        },
        "context_summary": context_summary,
        "suggested_prompts": [
            "How is my financial health score computed?",
            "Am I staying within my budget this month?",
            "What bills and subscriptions are coming up?",
            "How can I improve my savings rate?"
        ]
    }

def list_conversations(db: Session, user_id: int) -> list[dict]:
    rows = db.scalars(select(AIConversation).where(AIConversation.user_id == user_id).order_by(AIConversation.id.desc())).all()
    return [{
        "id": c.id,
        "title": c.title,
        "created_at": c.created_at,
    } for c in rows]

def get_conversation_messages(db: Session, user_id: int, conversation_id: int) -> list[dict]:
    conv = db.scalar(select(AIConversation).where(AIConversation.id == conversation_id, AIConversation.user_id == user_id))
    if not conv:
        return []
    messages = db.scalars(select(AIMessage).where(AIMessage.conversation_id == conv.id).order_by(AIMessage.id.asc())).all()
    return [{
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "created_at": m.created_at,
    } for m in messages]
