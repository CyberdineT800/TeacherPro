from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

# Base class for all models
class Base(DeclarativeBase):
    pass

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite+aiosqlite:///school_grading.db')

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Dependency to get database session
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Initialize database tables
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(100))
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=True)
    staff_title_id = Column(Integer, ForeignKey('staff_titles.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    teacher_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    class_id = Column(Integer, ForeignKey('classes.id'), nullable=False)

class TeacherSubject(Base):
    __tablename__ = 'teacher_subjects'
    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    subject_id = Column(Integer, ForeignKey('subjects.id'), nullable=False)

class SchoolClass(Base):
    __tablename__ = 'classes'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)
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
    gender = Column(Integer, nullable=False)  # 1=male, 2=female
    group_number = Column(Integer, default=1)  # 1 or 2
    class_id = Column(Integer, ForeignKey('classes.id'), nullable=False)
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
    class_id = Column(Integer, ForeignKey('classes.id'), nullable=False)
    subject_id = Column(Integer, ForeignKey('subjects.id'), nullable=False)
    quarter_id = Column(Integer, ForeignKey('quarters.id'), nullable=False)
    exam_name_id = Column(Integer, ForeignKey('exam_names.id'), nullable=False)
    exam_type_id = Column(Integer, ForeignKey('exam_types.id'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    is_bsb_exam = Column(Boolean, default=False)
    
    school_class = relationship('SchoolClass', back_populates='exams')
    subject = relationship('Subject')
    quarter = relationship('Quarter')
    exam_name = relationship('ExamName')
    exam_type = relationship('ExamType')
    teacher = relationship('Employee')
    questions = relationship('Question', back_populates='exam', cascade='all, delete-orphan')
    results = relationship('ExamResult', back_populates='exam', cascade='all, delete-orphan')

class Question(Base):
    __tablename__ = 'questions'
    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey('exams.id'), nullable=False)
    question_number = Column(Integer, nullable=False)
    question_type_id = Column(Integer, ForeignKey('question_types.id'), nullable=False)
    max_score = Column(Float, nullable=False)
    
    exam = relationship('Exam', back_populates='questions')
    question_type = relationship('QuestionType')

class ExamResult(Base):
    __tablename__ = 'exam_results'
    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey('exams.id'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False)
    score = Column(Float, nullable=False)
    
    exam = relationship('Exam', back_populates='results')
    student = relationship('Student')
    question = relationship('Question')