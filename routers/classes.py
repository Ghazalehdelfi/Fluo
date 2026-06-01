"""Teacher/student class and homework routes."""

import json
import uuid
import secrets as _secrets
import string as _string
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import (
    User,
    Language,
    Vocabulary,
    Grammar,
    Class,
    ClassStudent,
    Homework,
    HomeworkVocabRef,
    HomeworkGrammarRef,
    HomeworkGrammarQuestion,
    HomeworkTopic,
    HomeworkCompletion,
    SessionLocal,
)
from auth import get_current_user, require_teacher
from cost_tracker import TrackedOpenAI
from dependencies import get_db, get_api_key, get_native_language, get_user_level
from agents.grammar_practice_agent import GrammarPracticeAgent
from agents.logging_utils import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────


def _generate_class_code(length: int = 8) -> str:
    """Generate a random uppercase alphanumeric class code."""
    alphabet = _string.ascii_uppercase + _string.digits
    return "".join(_secrets.choice(alphabet) for _ in range(length))


def _homework_belongs_to_teacher(
    homework_id: int, teacher_id: int, db: Session
) -> Homework:
    hw = (
        db.query(Homework)
        .filter(Homework.id == homework_id, Homework.teacher_id == teacher_id)
        .first()
    )
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")
    return hw


def _class_belongs_to_teacher(class_id: int, teacher_id: int, db: Session) -> Class:
    cls = (
        db.query(Class)
        .filter(Class.id == class_id, Class.teacher_id == teacher_id)
        .first()
    )
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    return cls


# ── Pydantic models ───────────────────────────────────────────────


class ClassCreate(BaseModel):
    name: str
    language_id: Optional[int] = None


class HomeworkCreate(BaseModel):
    class_id: int
    name: str
    description: Optional[str] = None
    language_id: Optional[int] = None
    due_date: Optional[str] = None  # ISO date string


class HomeworkUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None


class VocabRefsBody(BaseModel):
    vocabulary_ids: List[int]


class GrammarRefsBody(BaseModel):
    grammar_ids: List[int]


class HomeworkQuestionItem(BaseModel):
    question_type: str
    question_text: str
    english_prompt: Optional[str] = None
    wrong_sentence: Optional[str] = None
    correct_answer: str
    explanation: Optional[str] = None
    highlighted_segments: Optional[str] = None  # JSON string
    order_index: int = 0


class HomeworkQuestionsBody(BaseModel):
    questions: List[HomeworkQuestionItem]


class HomeworkTopicBody(BaseModel):
    topic_text: str
    source: str = "custom"
    cluster_topic_id: Optional[int] = None


class HomeworkCompleteBody(BaseModel):
    exercise_type: str  # 'flashcards' | 'grammar' | 'conversation'
    score: Optional[float] = None


class AddStudentByEmailBody(BaseModel):
    email: str


class JoinClassBody(BaseModel):
    class_code: str


# ── Class endpoints (teacher) ─────────────────────────────────────


@router.post("/api/classes")
async def create_class(
    body: ClassCreate,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    if body.language_id:
        lang = (
            db.query(Language)
            .filter(Language.id == body.language_id, Language.user_id == teacher.id)
            .first()
        )
        if not lang:
            raise HTTPException(status_code=404, detail="Language not found")

    code = _generate_class_code()
    while db.query(Class).filter(Class.class_code == code).first():
        code = _generate_class_code()

    cls = Class(
        teacher_id=teacher.id,
        name=body.name,
        language_id=body.language_id,
        class_code=code,
    )
    db.add(cls)
    db.commit()
    db.refresh(cls)
    return {
        "id": cls.id,
        "name": cls.name,
        "class_code": cls.class_code,
        "language_id": cls.language_id,
        "created_at": cls.created_at.isoformat(),
    }


@router.get("/api/classes")
async def list_classes(
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    classes = db.query(Class).filter(Class.teacher_id == teacher.id).all()
    result = []
    for cls in classes:
        student_count = (
            db.query(ClassStudent).filter(ClassStudent.class_id == cls.id).count()
        )
        result.append(
            {
                "id": cls.id,
                "name": cls.name,
                "class_code": cls.class_code,
                "language_id": cls.language_id,
                "student_count": student_count,
                "created_at": cls.created_at.isoformat(),
            }
        )
    return result


@router.get("/api/classes/{class_id}")
async def get_class(
    class_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    cls = _class_belongs_to_teacher(class_id, teacher.id, db)
    student_rows = (
        db.query(ClassStudent).filter(ClassStudent.class_id == class_id).all()
    )
    students = []
    for row in student_rows:
        student = db.query(User).filter(User.id == row.student_id).first()
        if student:
            students.append(
                {
                    "id": student.id,
                    "email": student.email,
                    "joined_at": row.joined_at.isoformat(),
                }
            )
    homework_list = db.query(Homework).filter(Homework.class_id == class_id).all()
    return {
        "id": cls.id,
        "name": cls.name,
        "class_code": cls.class_code,
        "language_id": cls.language_id,
        "students": students,
        "homework": [
            {
                "id": hw.id,
                "name": hw.name,
                "due_date": hw.due_date.isoformat() if hw.due_date else None,
            }
            for hw in homework_list
        ],
    }


@router.post("/api/classes/{class_id}/students")
async def add_student_to_class(
    class_id: int,
    body: AddStudentByEmailBody,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    _class_belongs_to_teacher(class_id, teacher.id, db)
    student = db.query(User).filter(User.email == body.email).first()
    if not student:
        raise HTTPException(status_code=404, detail="No user found with that email")
    if student.role != "student":
        raise HTTPException(status_code=400, detail="That user is not a student")
    existing = (
        db.query(ClassStudent)
        .filter(
            ClassStudent.class_id == class_id, ClassStudent.student_id == student.id
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Student already in this class")
    db.add(ClassStudent(class_id=class_id, student_id=student.id))
    db.commit()
    return {"message": f"{student.email} added to class"}


@router.delete("/api/classes/{class_id}/students/{student_id}")
async def remove_student_from_class(
    class_id: int,
    student_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    _class_belongs_to_teacher(class_id, teacher.id, db)
    row = (
        db.query(ClassStudent)
        .filter(
            ClassStudent.class_id == class_id, ClassStudent.student_id == student_id
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Student not in this class")
    db.delete(row)
    db.commit()
    return {"message": "Student removed from class"}


@router.post("/api/classes/join")
async def join_class(
    body: JoinClassBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Student joins a class using a class code."""
    cls = db.query(Class).filter(Class.class_code == body.class_code.upper()).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Invalid class code")
    existing = (
        db.query(ClassStudent)
        .filter(ClassStudent.class_id == cls.id, ClassStudent.student_id == user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already enrolled in this class")
    db.add(ClassStudent(class_id=cls.id, student_id=user.id))
    db.commit()
    return {
        "message": f"Joined class '{cls.name}'",
        "class_id": cls.id,
        "class_name": cls.name,
    }


# ── Homework CRUD (teacher) ───────────────────────────────────────


@router.post("/api/homework")
async def create_homework(
    body: HomeworkCreate,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    _class_belongs_to_teacher(body.class_id, teacher.id, db)
    due = None
    if body.due_date:
        try:
            due = datetime.fromisoformat(body.due_date)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid due_date format (use ISO 8601)"
            )
    hw = Homework(
        class_id=body.class_id,
        teacher_id=teacher.id,
        name=body.name,
        description=body.description,
        language_id=body.language_id,
        due_date=due,
    )
    db.add(hw)
    db.commit()
    db.refresh(hw)
    return {
        "id": hw.id,
        "name": hw.name,
        "class_id": hw.class_id,
        "language_id": hw.language_id,
        "due_date": hw.due_date.isoformat() if hw.due_date else None,
        "created_at": hw.created_at.isoformat(),
    }


@router.get("/api/homework")
async def list_homework(
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    hws = db.query(Homework).filter(Homework.teacher_id == teacher.id).all()
    result = []
    for hw in hws:
        cls = db.query(Class).filter(Class.id == hw.class_id).first()
        vocab_count = (
            db.query(HomeworkVocabRef)
            .filter(HomeworkVocabRef.homework_id == hw.id)
            .count()
        )
        grammar_count = (
            db.query(HomeworkGrammarRef)
            .filter(HomeworkGrammarRef.homework_id == hw.id)
            .count()
        )
        topic_count = (
            db.query(HomeworkTopic).filter(HomeworkTopic.homework_id == hw.id).count()
        )
        result.append(
            {
                "id": hw.id,
                "name": hw.name,
                "description": hw.description,
                "class_id": hw.class_id,
                "class_name": cls.name if cls else None,
                "language_id": hw.language_id,
                "due_date": hw.due_date.isoformat() if hw.due_date else None,
                "created_at": hw.created_at.isoformat(),
                "vocab_count": vocab_count,
                "grammar_count": grammar_count,
                "topic_count": topic_count,
            }
        )
    return result


@router.get("/api/homework/{homework_id}")
async def get_homework(
    homework_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    hw = _homework_belongs_to_teacher(homework_id, teacher.id, db)
    cls = db.query(Class).filter(Class.id == hw.class_id).first()

    vocab_refs = (
        db.query(HomeworkVocabRef)
        .filter(HomeworkVocabRef.homework_id == homework_id)
        .all()
    )
    vocab_items = []
    for ref in vocab_refs:
        v = db.query(Vocabulary).filter(Vocabulary.id == ref.vocabulary_id).first()
        if v:
            vocab_items.append(
                {
                    "id": v.id,
                    "target_word": v.target_word,
                    "native_translation": v.native_translation,
                    "example_sentence": v.example_sentence,
                    "fluency_level": v.fluency_level,
                }
            )

    grammar_refs = (
        db.query(HomeworkGrammarRef)
        .filter(HomeworkGrammarRef.homework_id == homework_id)
        .all()
    )
    grammar_items = []
    for ref in grammar_refs:
        g = db.query(Grammar).filter(Grammar.id == ref.grammar_id).first()
        if g:
            questions = (
                db.query(HomeworkGrammarQuestion)
                .filter(
                    HomeworkGrammarQuestion.homework_id == homework_id,
                    HomeworkGrammarQuestion.grammar_id == ref.grammar_id,
                )
                .order_by(HomeworkGrammarQuestion.order_index)
                .all()
            )
            grammar_items.append(
                {
                    "id": g.id,
                    "concept_name": g.concept_name,
                    "description": g.description,
                    "examples": g.examples,
                    "fluency_level": g.fluency_level,
                    "questions_saved": len(questions),
                    "questions": [
                        {
                            "id": q.id,
                            "question_type": q.question_type,
                            "question_text": q.question_text,
                            "english_prompt": q.english_prompt,
                            "wrong_sentence": q.wrong_sentence,
                            "correct_answer": q.correct_answer,
                            "explanation": q.explanation,
                            "highlighted_segments": (
                                json.loads(q.highlighted_segments)
                                if q.highlighted_segments
                                else []
                            ),
                            "order_index": q.order_index,
                        }
                        for q in questions
                    ],
                }
            )

    topics = (
        db.query(HomeworkTopic).filter(HomeworkTopic.homework_id == homework_id).all()
    )

    completions = (
        db.query(HomeworkCompletion)
        .filter(HomeworkCompletion.homework_id == homework_id)
        .all()
    )
    completion_summary: dict = {}
    for c in completions:
        completion_summary[c.exercise_type] = (
            completion_summary.get(c.exercise_type, 0) + 1
        )

    return {
        "id": hw.id,
        "name": hw.name,
        "description": hw.description,
        "class_id": hw.class_id,
        "class_name": cls.name if cls else None,
        "language_id": hw.language_id,
        "due_date": hw.due_date.isoformat() if hw.due_date else None,
        "created_at": hw.created_at.isoformat(),
        "vocab": vocab_items,
        "grammar": grammar_items,
        "topics": [
            {
                "id": t.id,
                "topic_text": t.topic_text,
                "source": t.source,
                "cluster_topic_id": t.cluster_topic_id,
            }
            for t in topics
        ],
        "completion_summary": completion_summary,
    }


@router.put("/api/homework/{homework_id}")
async def update_homework(
    homework_id: int,
    body: HomeworkUpdate,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    hw = _homework_belongs_to_teacher(homework_id, teacher.id, db)
    if body.name is not None:
        hw.name = body.name
    if body.description is not None:
        hw.description = body.description
    if body.due_date is not None:
        try:
            hw.due_date = datetime.fromisoformat(body.due_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid due_date format")
    db.commit()
    return {"message": "Homework updated"}


@router.delete("/api/homework/{homework_id}")
async def delete_homework(
    homework_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    hw = _homework_belongs_to_teacher(homework_id, teacher.id, db)
    db.delete(hw)
    db.commit()
    return {"message": "Homework deleted"}


# ── Homework content refs (teacher) ──────────────────────────────


@router.post("/api/homework/{homework_id}/vocab-refs")
async def add_vocab_refs(
    homework_id: int,
    body: VocabRefsBody,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    _homework_belongs_to_teacher(homework_id, teacher.id, db)
    added = 0
    for vid in body.vocabulary_ids:
        vocab = db.query(Vocabulary).filter(Vocabulary.id == vid).first()
        if not vocab:
            continue
        lang = (
            db.query(Language)
            .filter(Language.id == vocab.language_id, Language.user_id == teacher.id)
            .first()
        )
        if not lang:
            continue
        existing = (
            db.query(HomeworkVocabRef)
            .filter(
                HomeworkVocabRef.homework_id == homework_id,
                HomeworkVocabRef.vocabulary_id == vid,
            )
            .first()
        )
        if not existing:
            db.add(HomeworkVocabRef(homework_id=homework_id, vocabulary_id=vid))
            added += 1
    db.commit()
    return {"message": f"{added} vocab item(s) attached"}


@router.delete("/api/homework/{homework_id}/vocab-refs/{vocab_id}")
async def remove_vocab_ref(
    homework_id: int,
    vocab_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    _homework_belongs_to_teacher(homework_id, teacher.id, db)
    row = (
        db.query(HomeworkVocabRef)
        .filter(
            HomeworkVocabRef.homework_id == homework_id,
            HomeworkVocabRef.vocabulary_id == vocab_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Vocab ref not found")
    db.delete(row)
    db.commit()
    return {"message": "Vocab ref removed"}


@router.post("/api/homework/{homework_id}/grammar-refs")
async def add_grammar_refs(
    homework_id: int,
    body: GrammarRefsBody,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    _homework_belongs_to_teacher(homework_id, teacher.id, db)
    added = 0
    for gid in body.grammar_ids:
        grammar = db.query(Grammar).filter(Grammar.id == gid).first()
        if not grammar:
            continue
        lang = (
            db.query(Language)
            .filter(Language.id == grammar.language_id, Language.user_id == teacher.id)
            .first()
        )
        if not lang:
            continue
        existing = (
            db.query(HomeworkGrammarRef)
            .filter(
                HomeworkGrammarRef.homework_id == homework_id,
                HomeworkGrammarRef.grammar_id == gid,
            )
            .first()
        )
        if not existing:
            db.add(HomeworkGrammarRef(homework_id=homework_id, grammar_id=gid))
            added += 1
    db.commit()
    return {"message": f"{added} grammar concept(s) attached"}


@router.delete("/api/homework/{homework_id}/grammar-refs/{grammar_id}")
async def remove_grammar_ref(
    homework_id: int,
    grammar_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    _homework_belongs_to_teacher(homework_id, teacher.id, db)
    row = (
        db.query(HomeworkGrammarRef)
        .filter(
            HomeworkGrammarRef.homework_id == homework_id,
            HomeworkGrammarRef.grammar_id == grammar_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Grammar ref not found")
    db.delete(row)
    db.query(HomeworkGrammarQuestion).filter(
        HomeworkGrammarQuestion.homework_id == homework_id,
        HomeworkGrammarQuestion.grammar_id == grammar_id,
    ).delete()
    db.commit()
    return {"message": "Grammar ref removed"}


@router.post("/api/homework/{homework_id}/grammar/{grammar_id}/generate-questions")
async def generate_homework_questions(
    homework_id: int,
    grammar_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Generate draft questions for a grammar concept (not saved yet)."""
    _homework_belongs_to_teacher(homework_id, teacher.id, db)

    ref = (
        db.query(HomeworkGrammarRef)
        .filter(
            HomeworkGrammarRef.homework_id == homework_id,
            HomeworkGrammarRef.grammar_id == grammar_id,
        )
        .first()
    )
    if not ref:
        raise HTTPException(
            status_code=404, detail="Grammar concept not attached to this homework"
        )

    grammar = db.query(Grammar).filter(Grammar.id == grammar_id).first()
    if not grammar:
        raise HTTPException(status_code=404, detail="Grammar concept not found")

    api_key = get_api_key()
    native_lang = get_native_language(db, teacher.id)
    user_level = get_user_level(db, teacher.id)

    lang = db.query(Language).filter(Language.id == grammar.language_id).first()
    target_language = lang.name if lang else "Unknown"

    # Auto-generate detail card if missing
    if not grammar.detail_card:
        session_id = str(uuid.uuid4())
        tracked_client = TrackedOpenAI(
            api_key, user_id=teacher.id, session_id=session_id, db_factory=SessionLocal
        )
        dc_prompt = f"""You are an expert language tutor creating a focused grammar study card for a language learner.

Return only this JSON — no preamble, no markdown fences:

{{
  "concept": "Concept name",
  "tagline": "One sentence: what this concept does in plain English",
  "breakdown": {{
    "structure": "The abstract pattern",
    "components": [
      {{ "part": "element", "role": "what it does", "from_trigger": "word from trigger" }}
    ]
  }},
  "core_rules": ["Rule stated simply"],
  "nuances": [{{ "observation": "A subtle point", "example": "Sentence illustrating it" }}],
  "examples": [{{ "sentence": "...", "translation": "...", "highlight": "..." }}],
  "common_errors": [{{ "wrong": "...", "right": "...", "why": "..." }}],
  "related_concepts": ["..."]
}}

Rules: If a field has no confident content set it to null. Never fabricate entries.

Concept: {grammar.concept_name}
Trigger phrase: {grammar.examples or grammar.description or "(none provided)"}
Target language: {target_language}
Learner level: {user_level}"""

        dc_response = tracked_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": dc_prompt}],
            temperature=0.3,
        )
        raw = dc_response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]
            raw = raw.strip()
        try:
            grammar.detail_card = json.dumps(json.loads(raw))
        except json.JSONDecodeError:
            grammar.detail_card = json.dumps(
                {
                    "concept": grammar.concept_name,
                    "description": grammar.description or "",
                }
            )
        db.commit()

    from openai import OpenAI as _OpenAI

    client = _OpenAI(api_key=api_key)
    agent = GrammarPracticeAgent(
        client,
        target_language=target_language,
        native_language=native_lang,
        level=user_level,
        fluency_level=grammar.fluency_level or "low",
    )

    try:
        detail_card = json.loads(grammar.detail_card)
    except (json.JSONDecodeError, ValueError):
        detail_card = {
            "concept": grammar.concept_name,
            "description": grammar.description,
        }

    questions = agent.generate_questions(detail_card)
    for i, q in enumerate(questions):
        q["order_index"] = i
        if "type" in q and "question_type" not in q:
            q["question_type"] = q.pop("type")
    return {"questions": questions}


@router.put("/api/homework/{homework_id}/grammar/{grammar_id}/questions")
async def save_homework_questions(
    homework_id: int,
    grammar_id: int,
    body: HomeworkQuestionsBody,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Save teacher-refined questions for a grammar concept within a homework."""
    _homework_belongs_to_teacher(homework_id, teacher.id, db)
    ref = (
        db.query(HomeworkGrammarRef)
        .filter(
            HomeworkGrammarRef.homework_id == homework_id,
            HomeworkGrammarRef.grammar_id == grammar_id,
        )
        .first()
    )
    if not ref:
        raise HTTPException(
            status_code=404, detail="Grammar concept not attached to this homework"
        )

    db.query(HomeworkGrammarQuestion).filter(
        HomeworkGrammarQuestion.homework_id == homework_id,
        HomeworkGrammarQuestion.grammar_id == grammar_id,
    ).delete()

    for item in body.questions:
        db.add(
            HomeworkGrammarQuestion(
                homework_id=homework_id,
                grammar_id=grammar_id,
                question_type=item.question_type,
                question_text=item.question_text,
                english_prompt=item.english_prompt,
                wrong_sentence=item.wrong_sentence,
                correct_answer=item.correct_answer,
                explanation=item.explanation,
                highlighted_segments=item.highlighted_segments,
                order_index=item.order_index,
            )
        )
    db.commit()
    return {"message": f"{len(body.questions)} question(s) saved"}


@router.post("/api/homework/{homework_id}/topics")
async def add_homework_topic(
    homework_id: int,
    body: HomeworkTopicBody,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    _homework_belongs_to_teacher(homework_id, teacher.id, db)
    topic = HomeworkTopic(
        homework_id=homework_id,
        topic_text=body.topic_text,
        source=body.source,
        cluster_topic_id=body.cluster_topic_id,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return {"id": topic.id, "topic_text": topic.topic_text, "source": topic.source}


@router.delete("/api/homework/{homework_id}/topics/{topic_id}")
async def remove_homework_topic(
    homework_id: int,
    topic_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    _homework_belongs_to_teacher(homework_id, teacher.id, db)
    topic = (
        db.query(HomeworkTopic)
        .filter(HomeworkTopic.id == topic_id, HomeworkTopic.homework_id == homework_id)
        .first()
    )
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    db.delete(topic)
    db.commit()
    return {"message": "Topic removed"}


@router.get("/api/homework/{homework_id}/completions")
async def get_homework_completions(
    homework_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Get per-student completion status for a homework (teacher monitoring)."""
    hw = _homework_belongs_to_teacher(homework_id, teacher.id, db)
    student_rows = (
        db.query(ClassStudent).filter(ClassStudent.class_id == hw.class_id).all()
    )

    result = []
    for row in student_rows:
        student = db.query(User).filter(User.id == row.student_id).first()
        if not student:
            continue
        completions = (
            db.query(HomeworkCompletion)
            .filter(
                HomeworkCompletion.homework_id == homework_id,
                HomeworkCompletion.student_id == student.id,
            )
            .all()
        )
        completion_map = {
            c.exercise_type: {
                "score": c.score,
                "completed_at": c.completed_at.isoformat(),
            }
            for c in completions
        }
        result.append(
            {
                "student_id": student.id,
                "student_email": student.email,
                "completions": completion_map,
            }
        )
    return {"homework_name": hw.name, "students": result}


# ── Student homework endpoints ────────────────────────────────────


@router.get("/api/student/homework")
async def list_student_homework(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all homework assigned to the student via their class enrollments."""
    enrollments = (
        db.query(ClassStudent).filter(ClassStudent.student_id == user.id).all()
    )
    result = []
    for enrollment in enrollments:
        cls = db.query(Class).filter(Class.id == enrollment.class_id).first()
        if not cls:
            continue
        for hw in db.query(Homework).filter(Homework.class_id == cls.id).all():
            completions = (
                db.query(HomeworkCompletion)
                .filter(
                    HomeworkCompletion.homework_id == hw.id,
                    HomeworkCompletion.student_id == user.id,
                )
                .all()
            )
            completion_map = {c.exercise_type: True for c in completions}

            vocab_count = (
                db.query(HomeworkVocabRef)
                .filter(HomeworkVocabRef.homework_id == hw.id)
                .count()
            )
            grammar_count = (
                db.query(HomeworkGrammarRef)
                .filter(HomeworkGrammarRef.homework_id == hw.id)
                .count()
            )
            topic_count = (
                db.query(HomeworkTopic)
                .filter(HomeworkTopic.homework_id == hw.id)
                .count()
            )

            result.append(
                {
                    "id": hw.id,
                    "name": hw.name,
                    "description": hw.description,
                    "class_name": cls.name,
                    "language_id": hw.language_id,
                    "due_date": hw.due_date.isoformat() if hw.due_date else None,
                    "created_at": hw.created_at.isoformat(),
                    "vocab_count": vocab_count,
                    "grammar_count": grammar_count,
                    "topic_count": topic_count,
                    "completions": completion_map,
                }
            )
    return result


@router.get("/api/student/homework/{homework_id}")
async def get_student_homework_detail(
    homework_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get homework detail for a student. Verifies enrollment."""
    hw = db.query(Homework).filter(Homework.id == homework_id).first()
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")

    enrollment = (
        db.query(ClassStudent)
        .filter(
            ClassStudent.class_id == hw.class_id, ClassStudent.student_id == user.id
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=403, detail="Not enrolled in this class")

    cls = db.query(Class).filter(Class.id == hw.class_id).first()

    vocab_refs = (
        db.query(HomeworkVocabRef)
        .filter(HomeworkVocabRef.homework_id == homework_id)
        .all()
    )
    vocab_items = []
    for ref in vocab_refs:
        v = db.query(Vocabulary).filter(Vocabulary.id == ref.vocabulary_id).first()
        if v:
            vocab_items.append(
                {
                    "id": v.id,
                    "target_word": v.target_word,
                    "native_translation": v.native_translation,
                    "example_sentence": v.example_sentence,
                }
            )

    grammar_refs = (
        db.query(HomeworkGrammarRef)
        .filter(HomeworkGrammarRef.homework_id == homework_id)
        .all()
    )
    grammar_items = []
    for ref in grammar_refs:
        g = db.query(Grammar).filter(Grammar.id == ref.grammar_id).first()
        if g:
            questions = (
                db.query(HomeworkGrammarQuestion)
                .filter(
                    HomeworkGrammarQuestion.homework_id == homework_id,
                    HomeworkGrammarQuestion.grammar_id == ref.grammar_id,
                )
                .order_by(HomeworkGrammarQuestion.order_index)
                .all()
            )
            grammar_items.append(
                {
                    "id": g.id,
                    "concept_name": g.concept_name,
                    "description": g.description,
                    "questions_count": len(questions),
                    "questions": [
                        {
                            "id": q.id,
                            "question_type": q.question_type,
                            "question_text": q.question_text,
                            "english_prompt": q.english_prompt,
                            "wrong_sentence": q.wrong_sentence,
                            "correct_answer": q.correct_answer,
                            "explanation": q.explanation,
                            "highlighted_segments": (
                                json.loads(q.highlighted_segments)
                                if q.highlighted_segments
                                else []
                            ),
                            "order_index": q.order_index,
                        }
                        for q in questions
                    ],
                }
            )

    topics = (
        db.query(HomeworkTopic).filter(HomeworkTopic.homework_id == homework_id).all()
    )

    completions = (
        db.query(HomeworkCompletion)
        .filter(
            HomeworkCompletion.homework_id == homework_id,
            HomeworkCompletion.student_id == user.id,
        )
        .all()
    )
    completion_map = {
        c.exercise_type: {"score": c.score, "completed_at": c.completed_at.isoformat()}
        for c in completions
    }

    return {
        "id": hw.id,
        "name": hw.name,
        "description": hw.description,
        "class_name": cls.name if cls else None,
        "language_id": hw.language_id,
        "due_date": hw.due_date.isoformat() if hw.due_date else None,
        "vocab": vocab_items,
        "grammar": grammar_items,
        "topics": [
            {"id": t.id, "topic_text": t.topic_text, "source": t.source} for t in topics
        ],
        "completions": completion_map,
    }


@router.post("/api/student/homework/{homework_id}/start-flashcards")
async def student_start_flashcards(
    homework_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Copy teacher's homework vocab into student's vocabulary library (skip duplicates),
    then return the deck for flashcard practice.
    """
    hw = db.query(Homework).filter(Homework.id == homework_id).first()
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")

    enrollment = (
        db.query(ClassStudent)
        .filter(
            ClassStudent.class_id == hw.class_id, ClassStudent.student_id == user.id
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=403, detail="Not enrolled in this class")
    if not hw.language_id:
        raise HTTPException(status_code=400, detail="Homework has no language set")

    student_lang = (
        db.query(Language)
        .filter(Language.user_id == user.id, Language.id == hw.language_id)
        .first()
    )
    if not student_lang:
        teacher_lang = db.query(Language).filter(Language.id == hw.language_id).first()
        if teacher_lang:
            student_lang = (
                db.query(Language)
                .filter(Language.user_id == user.id, Language.name == teacher_lang.name)
                .first()
            )
            if not student_lang:
                student_lang = Language(
                    user_id=user.id, name=teacher_lang.name, code=teacher_lang.code
                )
                db.add(student_lang)
                db.flush()

    if not student_lang:
        raise HTTPException(
            status_code=400, detail="Could not determine student language"
        )

    vocab_refs = (
        db.query(HomeworkVocabRef)
        .filter(HomeworkVocabRef.homework_id == homework_id)
        .all()
    )
    deck = []
    for ref in vocab_refs:
        teacher_vocab = (
            db.query(Vocabulary).filter(Vocabulary.id == ref.vocabulary_id).first()
        )
        if not teacher_vocab:
            continue
        existing = (
            db.query(Vocabulary)
            .filter(
                Vocabulary.language_id == student_lang.id,
                Vocabulary.target_word.ilike(teacher_vocab.target_word),
            )
            .first()
        )
        if not existing:
            new_vocab = Vocabulary(
                language_id=student_lang.id,
                target_word=teacher_vocab.target_word,
                native_translation=teacher_vocab.native_translation,
                example_sentence=teacher_vocab.example_sentence,
                fluency_level="low",
            )
            db.add(new_vocab)
            db.flush()
            deck.append(
                {
                    "id": new_vocab.id,
                    "target_word": new_vocab.target_word,
                    "native_translation": new_vocab.native_translation,
                    "example_sentence": new_vocab.example_sentence,
                    "fluency_level": new_vocab.fluency_level,
                }
            )
        else:
            deck.append(
                {
                    "id": existing.id,
                    "target_word": existing.target_word,
                    "native_translation": existing.native_translation,
                    "example_sentence": existing.example_sentence,
                    "fluency_level": existing.fluency_level,
                }
            )
    db.commit()
    return {"deck": deck, "language_id": student_lang.id}


@router.post("/api/student/homework/{homework_id}/complete")
async def student_complete_exercise(
    homework_id: int,
    body: HomeworkCompleteBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a student's completion of an exercise type within a homework."""
    hw = db.query(Homework).filter(Homework.id == homework_id).first()
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")

    enrollment = (
        db.query(ClassStudent)
        .filter(
            ClassStudent.class_id == hw.class_id, ClassStudent.student_id == user.id
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=403, detail="Not enrolled in this class")

    valid_types = {"flashcards", "grammar", "conversation"}
    if body.exercise_type not in valid_types:
        raise HTTPException(
            status_code=400, detail=f"exercise_type must be one of {valid_types}"
        )

    existing = (
        db.query(HomeworkCompletion)
        .filter(
            HomeworkCompletion.student_id == user.id,
            HomeworkCompletion.homework_id == homework_id,
            HomeworkCompletion.exercise_type == body.exercise_type,
        )
        .first()
    )
    if existing:
        existing.score = body.score
        existing.completed_at = datetime.utcnow()
    else:
        db.add(
            HomeworkCompletion(
                student_id=user.id,
                homework_id=homework_id,
                exercise_type=body.exercise_type,
                score=body.score,
            )
        )
    db.commit()
    return {"message": f"{body.exercise_type} marked as complete"}
