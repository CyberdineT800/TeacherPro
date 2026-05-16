from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import UniqueConstraint, Column, Integer, String, Text, Boolean, Float, DateTime, Date, ForeignKey, Index
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

class Base(DeclarativeBase):
    pass

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql+asyncpg://teacherpro:teacherpro@localhost:5432/teacherpro',
)

_is_sqlite = DATABASE_URL.startswith('sqlite')

if _is_sqlite:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        connect_args={"timeout": 30},
    )
else:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        pool_size=5,          # 4 workers × 5 = 20 base connections
        max_overflow=10,      # 4 workers × 10 = 40 burst; total max 60 << pg max_connections=200
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_timeout=30,      # raise after 30s if no connection available
    )

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Schema migrations are managed by Alembic (migrations/versions/).
    # Run `alembic upgrade head` during deployment to apply pending changes.
    # init_db() only handles table creation via create_all (safe for new deployments).

class School(Base):
    __tablename__ = 'schools'
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    address = Column(Text)
    phone = Column(String(50))
    email = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    employees = relationship('Employee', back_populates='school', cascade='all, delete-orphan')
    classes = relationship('SchoolClass', back_populates='school', cascade='all, delete-orphan')

class StaffTitle(Base):
    __tablename__ = 'staff_titles'
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False, unique=True)

    employees = relationship('Employee', back_populates='staff_title')

class Employee(Base):
    __tablename__ = 'employees'
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(100))
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=True, index=True)
    staff_title_id = Column(Integer, ForeignKey('staff_titles.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ai_enabled = Column(Boolean, default=False, nullable=False)
    ai_daily_limit = Column(Integer, default=3, nullable=False)
    ai_used_today = Column(Integer, default=0, nullable=False)
    ai_last_reset = Column(Date, nullable=True)

    ai_questions_daily_limit = Column(Integer, default=5, nullable=False)
    ai_questions_used_today = Column(Integer, default=0, nullable=False)
    ai_questions_last_reset = Column(Date, nullable=True)

    games_enabled = Column(Boolean, default=False, nullable=False)

    school = relationship('School', back_populates='employees')
    staff_title = relationship('StaffTitle', back_populates='employees')
    assigned_classes = relationship('SchoolClass', secondary='teacher_classes', back_populates='assigned_teachers')
    assigned_subjects = relationship('Subject', secondary='teacher_subjects', back_populates='assigned_teachers')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class TeacherClass(Base):
    __tablename__ = 'teacher_classes'
    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey('classes.id'), nullable=False, index=True)

class TeacherSubject(Base):
    __tablename__ = 'teacher_subjects'
    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey('subjects.id'), nullable=False, index=True)

class SchoolClass(Base):
    __tablename__ = 'classes'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=False, index=True)
    leader_first_name = Column(String(100), nullable=True)
    leader_last_name = Column(String(100), nullable=True)
    leader_phone = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    school = relationship('School', back_populates='classes')
    students = relationship('Student', back_populates='school_class', cascade='all, delete-orphan')
    exams = relationship('Exam', back_populates='school_class')
    assigned_teachers = relationship('Employee', secondary='teacher_classes', back_populates='assigned_classes')

class Student(Base):
    __tablename__ = 'students'
    id = Column(Integer, primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    gender = Column(Integer, nullable=False)
    group_number = Column(Integer, default=1)
    class_id = Column(Integer, ForeignKey('classes.id'), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    school_class = relationship('SchoolClass', back_populates='students')

class Subject(Base):
    __tablename__ = 'subjects'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)

    assigned_teachers = relationship('Employee', secondary='teacher_subjects', back_populates='assigned_subjects')

class Quarter(Base):
    __tablename__ = 'quarters'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    order_num = Column(Integer, nullable=False)

class ExamName(Base):
    __tablename__ = 'exam_names'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)

class ExamType(Base):
    __tablename__ = 'exam_types'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)

class QuestionType(Base):
    __tablename__ = 'question_types'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)

class Exam(Base):
    __tablename__ = 'exams'
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey('classes.id'), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey('subjects.id'), nullable=False, index=True)
    quarter_id = Column(Integer, ForeignKey('quarters.id'), nullable=True)
    exam_name_id = Column(Integer, ForeignKey('exam_names.id'), nullable=False)
    exam_type_id = Column(Integer, ForeignKey('exam_types.id'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    is_bsb_exam = Column(Boolean, default=False)
    is_chsb_exam = Column(Boolean, default=False)
    is_project_exam = Column(Boolean, default=False)
    chsb_config = Column(Text, nullable=True)

    period = Column(String(200), nullable=True)
    difficulty = Column(String(50), nullable=True)
    exam_date = Column(String(20), nullable=True)

    gender_filter = Column(Integer, nullable=True)
    group_filter = Column(Integer, nullable=True)
    variant = Column(Integer, default=1)

    school_class = relationship('SchoolClass', back_populates='exams')
    subject = relationship('Subject')
    quarter = relationship('Quarter')
    exam_name = relationship('ExamName')
    exam_type = relationship('ExamType')
    teacher = relationship('Employee')
    questions = relationship('Question', back_populates='exam', cascade='all, delete-orphan')
    results = relationship('ExamResult', back_populates='exam', cascade='all, delete-orphan')

class CHSBQuestionAssignment(Base):
    __tablename__ = 'chsb_question_assignments'
    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey('exams.id'), nullable=False, index=True)
    question_number = Column(Integer, nullable=False)
    question_type_id = Column(Integer, ForeignKey('question_types.id'), nullable=False)
    max_score = Column(Float, nullable=False)

    exam = relationship('Exam')
    question_type = relationship('QuestionType')

class Question(Base):
    __tablename__ = 'questions'
    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey('exams.id'), nullable=False, index=True)
    question_number = Column(Integer, nullable=False)
    question_type_id = Column(Integer, ForeignKey('question_types.id'), nullable=False)
    max_score = Column(Float, nullable=False)

    exam = relationship('Exam', back_populates='questions')
    question_type = relationship('QuestionType')

class ExamResult(Base):
    __tablename__ = 'exam_results'
    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey('exams.id'), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False, index=True)
    score = Column(Float, nullable=False)

    exam = relationship('Exam', back_populates='results')
    student = relationship('Student')
    question = relationship('Question')

class AIPresentation(Base):
    __tablename__ = 'ai_presentations'
    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey('subjects.id'), nullable=True)
    subject_name = Column(String(100), nullable=False)
    grade = Column(Integer, nullable=False)
    topic = Column(String(300), nullable=False)
    language = Column(String(10), nullable=False, default='uz')
    template = Column(String(50), nullable=False, default='cosmos')
    content = Column(Text, nullable=False)
    slides_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    share_token = Column(String(64), nullable=True, unique=True, index=True)

    teacher = relationship('Employee')
    subject = relationship('Subject')

class AIQuestionSet(Base):
    __tablename__ = 'ai_question_sets'
    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    subject_name = Column(String(100), nullable=False)
    grade = Column(Integer, nullable=False)
    topic = Column(String(300), nullable=False)
    language = Column(String(10), nullable=False, default='uz')
    question_type = Column(String(10), nullable=False, default='test')
    question_count = Column(Integer, nullable=False, default=10)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    teacher = relationship('Employee')

Index('ix_exam_results_exam_student', ExamResult.exam_id, ExamResult.student_id)
Index('ix_students_class_group', Student.class_id, Student.group_number)
Index('ix_ai_presentations_teacher_created', AIPresentation.teacher_id, AIPresentation.created_at)
Index('ix_ai_question_sets_teacher_created', AIQuestionSet.teacher_id, AIQuestionSet.created_at)


# ============================================================================
# GAME MODELS
# ============================================================================

class GameSession(Base):
    """A single Quiz Race game created by a teacher."""
    __tablename__ = 'game_sessions'
    id = Column(Integer, primary_key=True)
    code = Column(String(8), unique=True, nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    subject_name = Column(String(100), nullable=True)
    grade = Column(Integer, nullable=True)
    time_per_question = Column(Integer, default=20, nullable=False)   # seconds
    # pending → lobby → playing → finished
    status = Column(String(20), default='pending', nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    teacher = relationship('Employee')
    questions = relationship(
        'GameQuestion', back_populates='session',
        cascade='all, delete-orphan',
        order_by='GameQuestion.order',
    )
    participants = relationship(
        'GameParticipant', back_populates='session',
        cascade='all, delete-orphan',
    )


class GameQuestion(Base):
    """One multiple-choice question belonging to a GameSession."""
    __tablename__ = 'game_questions'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('game_sessions.id'), nullable=False, index=True)
    order = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    option_a = Column(String(500), nullable=False)
    option_b = Column(String(500), nullable=False)
    option_c = Column(String(500), nullable=False)
    option_d = Column(String(500), nullable=False)
    correct_option = Column(Integer, nullable=False)   # 0=A 1=B 2=C 3=D
    points = Column(Integer, default=10, nullable=False)

    session = relationship('GameSession', back_populates='questions')


class GameParticipant(Base):
    """Final result record for one student in a completed GameSession."""
    __tablename__ = 'game_participants'
    __table_args__ = (
        UniqueConstraint('session_id', 'nickname', name='uq_participant_session_nickname'),
    )
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('game_sessions.id'), nullable=False, index=True)
    nickname = Column(String(100), nullable=False)
    total_score = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    wrong_answers = Column(Integer, default=0)
    rank = Column(Integer, nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow)

    session = relationship('GameSession', back_populates='participants')


Index('ix_game_sessions_teacher_created', GameSession.teacher_id, GameSession.created_at)
Index('ix_game_sessions_status', GameSession.status)
Index('ix_game_questions_session_order', GameQuestion.session_id, GameQuestion.order)


# ============================================================================
# ANNOUNCEMENT MODEL
# ============================================================================

class Announcement(Base):
    """Admin-managed announcements shown on the public home page."""
    __tablename__ = 'announcements'
    id          = Column(Integer, primary_key=True)
    title       = Column(String(200), nullable=False)
    body        = Column(Text, nullable=True)
    image_url   = Column(Text, nullable=True)
    image_url_2 = Column(Text, nullable=True)
    image_url_3 = Column(Text, nullable=True)
    badge       = Column(String(60), nullable=True)   # e.g. "Yangi", "Muhim"
    link_url    = Column(String(500), nullable=True)  # optional "Read more" link
    is_active   = Column(Boolean, default=True,  nullable=False, index=True)
    order_num   = Column(Integer,  default=0,    nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow)

Index('ix_announcements_active_order', Announcement.is_active, Announcement.order_num)
