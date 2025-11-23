# TeacherPro - School Grading Management System

## FastAPI Version 2.0.0

A modern, async school grading management system built with FastAPI and async SQLAlchemy.

## Features

- 🚀 **Async Operations** - All database and I/O operations are asynchronous
- 👥 **Role-Based Access** - Admin and Teacher roles with different permissions
- 📊 **Exam Management** - Create exams, enter scores, view results
- 📄 **Report Generation** - Export results to Excel, PDF, and Word formats
- 🏫 **School Management** - Manage schools, classes, students, and employees
- 📁 **Excel Import** - Bulk import students from Excel files

## Quick Start

### Installation

1. Install dependencies:
```powershell
pip install -r requirements.txt
```

2. Run the application:
```powershell
uvicorn main:app --reload
```

3. Open your browser:
```
http://127.0.0.1:8000
```

## Project Structure

```
TeacherPro/
├── main.py                 # FastAPI application entry point
├── models.py               # Async SQLAlchemy models
├── dependencies.py         # Authentication & dependencies
├── utils.py                # Async utility functions
├── config.py               # Configuration
├── requirements.txt        # Python dependencies
├── routers/
│   ├── auth.py            # Authentication routes
│   ├── admin.py           # Admin routes
│   └── teacher.py         # Teacher routes
├── templates/             # Jinja2 templates
├── static/                # Static files (CSS, JS)
└── instance/              # Database file
```

## API Documentation

FastAPI provides automatic interactive API documentation:

- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`

## User Roles

### Admin
- Manage schools, employees, classes, and students
- Manage reference data (subjects, quarters, exam types, etc.)
- Full system access

### Teacher
- Create and manage exams
- Enter student scores
- View and download exam results
- Access only their school's classes

## Technology Stack

- **Framework:** FastAPI 0.115+
- **Server:** Uvicorn (ASGI)
- **Database:** SQLite with async support (aiosqlite)
- **ORM:** SQLAlchemy 2.0+ (async)
- **Templates:** Jinja2
- **Document Generation:** openpyxl, reportlab, python-docx
- **Data Processing:** pandas

## Environment Variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite+aiosqlite:///school_grading.db
```

## Development

### Running with auto-reload:
```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Running in production:
```powershell
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Migration from Flask

This project has been migrated from Flask to FastAPI. Key improvements:

- ⚡ **Performance:** All operations are now async
- 🎯 **Organization:** Routes separated into logical modules
- 🔧 **Maintainability:** Better dependency injection and code structure
- 🚀 **Modern:** Using latest async Python patterns

See [walkthrough.md](file:///C:/Users/Javohir%20Abdugafforov/.gemini/antigravity/brain/e50426c8-5d95-414f-9c60-ef55735e8cc6/walkthrough.md) for complete migration details.

## License

All rights reserved.

## Support

For issues or questions, please contact the development team.
