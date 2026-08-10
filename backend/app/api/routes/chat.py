"""Authenticated persistence for user chats and messages."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.db.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.chat import Chat
from app.models.message import Message
from app.models.user import User
from app.schemas.chat import ChatCreate, MessageCreate


router = APIRouter(prefix="/chats", tags=["Chats"])


def _owned_chat(db: Session, chat_id: int, user_id: int) -> Chat:
    chat = (
        db.query(Chat)
        .options(joinedload(Chat.messages))
        .filter(Chat.id == chat_id, Chat.user_id == user_id)
        .first()
    )
    if not chat:
        raise HTTPException(404, "Chat not found")
    return chat


def _chat_payload(chat: Chat, include_messages: bool = False) -> dict:
    result = {
        "id": chat.id,
        "title": chat.title,
        "created_at": chat.created_at,
        "updated_at": chat.updated_at,
    }
    if include_messages:
        result["messages"] = [
            {
                "id": message.id,
                "sender": message.sender,
                "content": message.message,
                "created_at": message.created_at,
            }
            for message in sorted(chat.messages, key=lambda item: item.created_at)
        ]
    return result


@router.post("")
def create_chat(
    request: ChatCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = Chat(user_id=current_user.id, title=request.title.strip())
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return _chat_payload(chat, include_messages=True)


@router.get("")
def list_chats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chats = (
        db.query(Chat)
        .filter(Chat.user_id == current_user.id)
        .order_by(Chat.updated_at.desc())
        .all()
    )
    return [_chat_payload(chat) for chat in chats]


@router.get("/{chat_id}")
def get_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _chat_payload(_owned_chat(db, chat_id, current_user.id), include_messages=True)


@router.post("/{chat_id}/messages")
def add_user_message(
    chat_id: int,
    request: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = _owned_chat(db, chat_id, current_user.id)
    message = Message(chat_id=chat.id, sender="user", message=request.content.strip())
    chat.updated_at = datetime.now(timezone.utc)
    db.add(message)
    db.commit()
    db.refresh(message)
    return {
        "id": message.id,
        "chat_id": chat.id,
        "sender": message.sender,
        "content": message.message,
        "created_at": message.created_at,
    }


@router.delete("/{chat_id}")
def delete_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = _owned_chat(db, chat_id, current_user.id)
    db.delete(chat)
    db.commit()
    return {"message": "Chat deleted", "chat_id": chat_id}
