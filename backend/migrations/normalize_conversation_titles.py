"""Normalize existing text-analysis titles for the Recents sidebar."""

from app.db.database import SessionLocal
from app.models.quick_response import QuickResponse
from app.models.upload_session import UploadSession
from app.models.report import Report  # noqa: F401
from app.models.medical_image import MedicalImage  # noqa: F401
from app.models.summary import Summary  # noqa: F401
from app.models.chat_history import ChatHistory  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.chat import Chat  # noqa: F401
from app.models.message import Message  # noqa: F401
from app.services.conversation_responses import normalize_message


def main() -> None:
    with SessionLocal() as db:
        intents = {
            item.trigger_phrase: item.intent
            for item in db.query(QuickResponse).filter(QuickResponse.active.is_(True)).all()
        }
        sessions = db.query(UploadSession).filter(UploadSession.input_type == "text").all()
        updated = 0
        for session in sessions:
            query = " ".join((session.original_query or "").split())
            intent = intents.get(normalize_message(query)) if query else None
            if intent == "greeting":
                title = "Greeting"
            else:
                title = "General enquiry — " + (" ".join(query.split()[:8]) or "Oncology question")
            title = title[:255]
            if session.session_name != title:
                session.session_name = title
                updated += 1
        db.commit()
    print(f"Normalized {updated} existing text conversation titles.")


if __name__ == "__main__":
    main()
