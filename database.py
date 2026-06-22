import os
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    ForeignKey,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

DATABASE_URL = os.environ["DATABASE_URL"]  # PostgreSQL connection string (Supabase)

engine = create_engine(
    DATABASE_URL,
    connect_args={"sslmode": "require"},
    pool_pre_ping=True,    # detect and discard stale connections before use
    pool_size=5,           # base connections kept open
    max_overflow=5,        # up to 10 total (safe under Supabase free tier's 60-conn limit)
    pool_recycle=1800,     # recycle connections every 30 min to avoid server-side timeouts
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Supported languages with ISO 639-1 codes for Whisper STT
SUPPORTED_LANGUAGES = {
    "Turkish": "tr",
    "Spanish": "es",
    "French": "fr",
    "Persian": "fa",
    "Korean": "kr",
    "Japanese": "jp",
    "German": "de",
}

# Native language options
NATIVE_LANGUAGES = [
    "English",
    "Spanish",
    "French",
    "German",
    "Turkish",
    "Persian",
    "Arabic",
    "Chinese",
]


# ── User model ──────────────────────────────────────────────────


class User(Base):
    """Registered user account."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    credits_balance = Column(Float, default=0.0)
    stripe_customer_id = Column(String, nullable=True, unique=True)
    role = Column(String, default="student", nullable=False)  # 'student' | 'teacher'
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    settings = relationship(
        "Settings", back_populates="user", cascade="all, delete-orphan"
    )
    languages = relationship(
        "Language", back_populates="user", cascade="all, delete-orphan"
    )
    usage_logs = relationship(
        "UsageLog", back_populates="user", cascade="all, delete-orphan"
    )


# ── Existing models (now scoped to user) ────────────────────────


class Settings(Base):
    """Per-user key/value settings (e.g. native_language)."""

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key = Column(String, index=True)
    value = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="settings")

    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_user_setting"),)


class Language(Base):
    """Languages a specific user is learning."""

    __tablename__ = "languages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, index=True)  # e.g., "Turkish", "Spanish"
    code = Column(String)  # ISO 639-1 code for STT
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="languages")

    # Relationships
    vocabulary = relationship(
        "Vocabulary", back_populates="language", cascade="all, delete-orphan"
    )
    grammar = relationship(
        "Grammar", back_populates="language", cascade="all, delete-orphan"
    )
    conversations = relationship(
        "Conversation", back_populates="language", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_language"),)


class Vocabulary(Base):
    __tablename__ = "vocabulary"

    id = Column(Integer, primary_key=True, index=True)
    language_id = Column(Integer, ForeignKey("languages.id"), nullable=False)
    target_word = Column(String, index=True)  # Word in target language
    native_translation = Column(String)  # Translation in native language
    example_sentence = Column(Text, nullable=True)
    fluency_level = Column(String, default="low")  # low, medium, high
    times_practiced = Column(Integer, default=0)
    times_correct = Column(Integer, default=0)
    last_practiced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    embedding = Column(
        Text, nullable=True
    )  # JSON array of floats from text-embedding-3-small

    language = relationship("Language", back_populates="vocabulary")


class Grammar(Base):
    __tablename__ = "grammar"

    id = Column(Integer, primary_key=True, index=True)
    language_id = Column(Integer, ForeignKey("languages.id"), nullable=False)
    concept_name = Column(String, index=True)
    description = Column(Text)
    examples = Column(Text, nullable=True)
    detail_card = Column(Text, nullable=True)  # JSON: generated detailed grammar card
    embedding = Column(
        Text, nullable=True
    )  # JSON array of floats from text-embedding-3-small
    fluency_level = Column(String, default="low")  # low, medium, high
    times_practiced = Column(Integer, default=0)
    times_correct = Column(Integer, default=0)
    last_practiced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    language = relationship("Language", back_populates="grammar")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    language_id = Column(Integer, ForeignKey("languages.id"), nullable=True)
    lesson_plan = Column(Text)
    transcript = Column(Text)
    analysis = Column(Text, nullable=True)
    vocab_used = Column(Text)  # JSON list of vocab IDs
    grammar_used = Column(Text)  # JSON list of grammar IDs
    total_cost_usd = Column(Float, default=0.0)  # Total API cost for this session
    created_at = Column(DateTime, default=datetime.utcnow)

    language = relationship("Language", back_populates="conversations")


# ── Usage / billing models ──────────────────────────────────────


class UsageLog(Base):
    """Per-API-call cost tracking for billing."""

    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(String, nullable=True)  # UUID of the active session
    model = Column(String, nullable=False)  # gpt-4o, whisper-1, tts-1
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    audio_seconds = Column(Float, default=0.0)  # For whisper
    characters = Column(Integer, default=0)  # For TTS
    cost_usd = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    charged = Column(
        Float, default=0.0
    )  # Amount actually charged to user after multiplier
    user = relationship("User", back_populates="usage_logs")


class ConversationTopic(Base):
    """Pre-computed conversation topics generated by clustering vocabulary embeddings."""

    __tablename__ = "conversation_topics"

    id = Column(Integer, primary_key=True, index=True)
    language_id = Column(Integer, ForeignKey("languages.id"), nullable=False)
    cluster_id = Column(Integer, nullable=False)  # k-means cluster index (0-based)
    theme = Column(String, nullable=False)  # e.g. "Food & Dining"
    topic = Column(Text, nullable=False)  # e.g. "Ordering at a restaurant"
    vocab_ids = Column(
        Text, nullable=False
    )  # JSON array of vocabulary IDs in this cluster
    generated_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    language = relationship("Language")


# ── Teacher / Student / Homework models ─────────────────────────


class Class(Base):
    """A teacher's class group."""

    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    language_id = Column(Integer, ForeignKey("languages.id"), nullable=True)
    class_code = Column(String(12), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    students = relationship(
        "ClassStudent", back_populates="class_", cascade="all, delete-orphan"
    )
    homework = relationship(
        "Homework", back_populates="class_", cascade="all, delete-orphan"
    )


class ClassStudent(Base):
    """Many-to-many: students enrolled in a class."""

    __tablename__ = "class_students"

    class_id = Column(Integer, ForeignKey("classes.id"), primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    joined_at = Column(DateTime, default=datetime.utcnow)

    class_ = relationship("Class", back_populates="students")


class Homework(Base):
    """A homework assignment created by a teacher for a class."""

    __tablename__ = "homework"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    language_id = Column(Integer, ForeignKey("languages.id"), nullable=True)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    class_ = relationship("Class", back_populates="homework")
    vocab_refs = relationship(
        "HomeworkVocabRef", back_populates="homework", cascade="all, delete-orphan"
    )
    grammar_refs = relationship(
        "HomeworkGrammarRef", back_populates="homework", cascade="all, delete-orphan"
    )
    grammar_questions = relationship(
        "HomeworkGrammarQuestion",
        back_populates="homework",
        cascade="all, delete-orphan",
    )
    topics = relationship(
        "HomeworkTopic", back_populates="homework", cascade="all, delete-orphan"
    )
    completions = relationship(
        "HomeworkCompletion", back_populates="homework", cascade="all, delete-orphan"
    )


class HomeworkVocabRef(Base):
    """Reference from a homework to one of the teacher's vocabulary items."""

    __tablename__ = "homework_vocab_refs"

    homework_id = Column(Integer, ForeignKey("homework.id"), primary_key=True)
    vocabulary_id = Column(Integer, ForeignKey("vocabulary.id"), primary_key=True)

    homework = relationship("Homework", back_populates="vocab_refs")
    vocabulary = relationship("Vocabulary")


class HomeworkGrammarRef(Base):
    """Reference from a homework to one of the teacher's grammar items."""

    __tablename__ = "homework_grammar_refs"

    homework_id = Column(Integer, ForeignKey("homework.id"), primary_key=True)
    grammar_id = Column(Integer, ForeignKey("grammar.id"), primary_key=True)

    homework = relationship("Homework", back_populates="grammar_refs")
    grammar = relationship("Grammar")


class HomeworkGrammarQuestion(Base):
    """A teacher-refined grammar question stored persistently for a homework."""

    __tablename__ = "homework_grammar_questions"

    id = Column(Integer, primary_key=True, index=True)
    homework_id = Column(Integer, ForeignKey("homework.id"), nullable=False)
    grammar_id = Column(Integer, ForeignKey("grammar.id"), nullable=False)
    question_type = Column(String(30), nullable=False)  # 'translation' | 'correction'
    question_text = Column(Text, nullable=False)
    english_prompt = Column(Text, nullable=True)
    wrong_sentence = Column(Text, nullable=True)
    correct_answer = Column(Text, nullable=False)
    explanation = Column(Text, nullable=True)
    highlighted_segments = Column(Text, nullable=True)  # JSON
    order_index = Column(Integer, default=0)

    homework = relationship("Homework", back_populates="grammar_questions")


class HomeworkTopic(Base):
    """A conversation topic attached to a homework."""

    __tablename__ = "homework_topics"

    id = Column(Integer, primary_key=True, index=True)
    homework_id = Column(Integer, ForeignKey("homework.id"), nullable=False)
    topic_text = Column(Text, nullable=False)
    source = Column(String(20), default="custom")  # 'custom' | 'clustered'
    cluster_topic_id = Column(
        Integer, ForeignKey("conversation_topics.id"), nullable=True
    )

    homework = relationship("Homework", back_populates="topics")


class HomeworkCompletion(Base):
    """Tracks a student's completion of one exercise type within a homework."""

    __tablename__ = "homework_completions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    homework_id = Column(Integer, ForeignKey("homework.id"), nullable=False)
    exercise_type = Column(
        String(30), nullable=False
    )  # 'flashcards'|'grammar'|'conversation'
    completed_at = Column(DateTime, default=datetime.utcnow)
    score = Column(Float, nullable=True)

    homework = relationship("Homework", back_populates="completions")

    __table_args__ = (
        UniqueConstraint(
            "student_id", "homework_id", "exercise_type", name="uq_homework_completion"
        ),
    )


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
