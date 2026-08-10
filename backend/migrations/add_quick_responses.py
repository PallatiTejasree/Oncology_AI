"""Create and seed database-managed non-clinical chat responses."""

from sqlalchemy import text

from app.db.database import engine


RESPONSES = {
    "greeting": {
        "hi": "Hello! How can I help you with your oncology report or medical image today?",
        "hello": "Hello! How can I help you with your oncology report or medical image today?",
        "hey": "Hello! How can I help you with your oncology report or medical image today?",
        "hiya": "Hello! How can I help you with your oncology report or medical image today?",
        "hey there": "Hello! How can I help you with your oncology report or medical image today?",
        "hello there": "Hello! How can I help you with your oncology report or medical image today?",
        "good morning": "Good morning! How can I help you with your oncology report, medical image, or cancer-related question today?",
        "morning": "Good morning! How can I help you with your oncology report, medical image, or cancer-related question today?",
        "good afternoon": "Good afternoon! How can I help you with your oncology report, medical image, or cancer-related question today?",
        "afternoon": "Good afternoon! How can I help you with your oncology report, medical image, or cancer-related question today?",
        "good evening": "Good evening! How can I help you with your oncology report, medical image, or cancer-related question today?",
        "evening": "Good evening! How can I help you with your oncology report, medical image, or cancer-related question today?",
        "good night": "Good night! I’ll be here when you are ready to review another oncology report, image, or question.",
    },
    "wellbeing": {
        "how are you": "I'm ready to help. You can ask a question or upload an oncology report or medical image.",
        "how are you doing": "I'm ready to help. You can ask a question or upload an oncology report or medical image.",
        "how's it going": "I'm ready to help. You can ask a question or upload an oncology report or medical image.",
        "hows it going": "I'm ready to help. You can ask a question or upload an oncology report or medical image.",
    },
    "help": {
        "help": "I can summarize oncology reports, review uploaded medical images, retrieve similar evidence, and answer follow-up questions. Upload a PDF or image, or type your clinical question to begin.",
        "can you help me": "Absolutely. You can ask about a cancer diagnosis, report, test result, or supported medical image. I can explain the available evidence in plain language.",
        "can you help me please": "Absolutely. You can ask about a cancer diagnosis, report, test result, or supported medical image. I can explain the available evidence in plain language.",
        "what can you do": "I can summarize oncology reports, review uploaded medical images, retrieve similar evidence, and answer follow-up questions. Upload a PDF or image, or type your clinical question to begin.",
        "how can you help": "I can summarize oncology reports, review uploaded medical images, retrieve similar evidence, and answer follow-up questions. Upload a PDF or image, or type your clinical question to begin.",
        "what do you do": "I can summarize oncology reports, review uploaded medical images, retrieve similar evidence, and answer follow-up questions. Upload a PDF or image, or type your clinical question to begin.",
    },
    "thanks": {
        "thanks": "You're welcome! Let me know if you would like help with another report, image, or clinical question.",
        "thank you": "You're very welcome. If you have another report, result, or question, share it and I’ll help explain the available information.",
        "thank you so much": "You're very welcome. If you have another report, result, or question, share it and I’ll help explain the available information.",
        "thanks a lot": "You're welcome! Let me know if you would like help with another report, image, or clinical question.",
        "much appreciated": "You're welcome! Let me know if you would like help with another report, image, or clinical question.",
    },
    "acknowledgement": {
        "ok": "Understood. What would you like to review next?",
        "okay": "Understood. What would you like to review next?",
        "alright": "Understood. What would you like to review next?",
        "got it": "Understood. What would you like to review next?",
        "understood": "Understood. What would you like to review next?",
        "sounds good": "Understood. What would you like to review next?",
    },
    "identity": {
        "who are you": "I'm Oncology AI, a clinical decision-support assistant for reviewing oncology reports, medical images, and related evidence. I do not replace professional medical judgment.",
        "what are you": "I'm Oncology AI, a clinical decision-support assistant for reviewing oncology reports, medical images, and related evidence. I do not replace professional medical judgment.",
        "tell me about yourself": "I'm Oncology AI, a clinical decision-support assistant for reviewing oncology reports, medical images, and related evidence. I do not replace professional medical judgment.",
    },
    "goodbye": {
        "bye": "Goodbye! Take care, and return whenever you need clinical decision support.",
        "goodbye": "Goodbye! Take care, and return whenever you need clinical decision support.",
        "see you": "Goodbye! Take care, and return whenever you need clinical decision support.",
        "see you later": "Goodbye! Take care, and return whenever you need clinical decision support.",
        "talk to you later": "Goodbye! Take care, and return whenever you need clinical decision support.",
    },
}


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS quick_responses (
    id SERIAL PRIMARY KEY,
    intent VARCHAR(50) NOT NULL,
    trigger_phrase VARCHAR(255) NOT NULL UNIQUE,
    response_text TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


def main() -> None:
    with engine.begin() as connection:
        connection.execute(text(CREATE_TABLE))
        connection.execute(text("ALTER TABLE quick_responses ALTER COLUMN active SET DEFAULT TRUE"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_quick_responses_intent ON quick_responses (intent)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_quick_responses_active ON quick_responses (active)"))
        for intent, entries in RESPONSES.items():
            for trigger, response in entries.items():
                connection.execute(
                    text(
                        """INSERT INTO quick_responses (intent, trigger_phrase, response_text, active)
                        VALUES (:intent, :trigger, :response, TRUE)
                        ON CONFLICT (trigger_phrase) DO UPDATE SET
                            intent = EXCLUDED.intent,
                            response_text = EXCLUDED.response_text,
                            active = TRUE,
                            updated_at = NOW()"""
                    ),
                    {"intent": intent, "trigger": trigger, "response": response},
                )
    print(f"Quick-response migration applied: {sum(map(len, RESPONSES.values()))} phrases seeded.")


if __name__ == "__main__":
    main()
