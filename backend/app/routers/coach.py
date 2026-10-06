from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.clock import user_today
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.core import User
from app.services import coach as svc
from app.services import nl_parser

router = APIRouter(prefix="/coach", tags=["coach"])

class ChatIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=1000)
    conversation_id: int | None = None

class QuickAddIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)

@router.post("/chat", summary="Chat with AI Money Coach")
def chat(
    body: ChatIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = user_today(user)
    return svc.ask_coach(db, user, body.prompt, today, body.conversation_id)

@router.get("/conversations", summary="List past conversations with AI Coach")
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_conversations(db, user.id)

@router.get("/conversations/{conversation_id}", summary="Get messages in a conversation")
def get_conversation(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.get_conversation_messages(db, user.id, conversation_id)

@router.post("/quick-add", summary="Parse quick add text into structured transaction fields")
def parse_quick_add(
    body: QuickAddIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = user_today(user)
    return nl_parser.parse_quick_add(body.text, user, today, db)

@router.get("/nl-search", summary="Parse natural language search query into transaction filter parameters")
def nl_search(
    q: str,
    user: User = Depends(get_current_user),
):
    today = user_today(user)
    return nl_parser.parse_nl_search(q, today)
