from main import app, db
from models import School, Employee, StaffTitle, SchoolClass, Student, Subject, Quarter, ExamName, ExamType, QuestionType

def init_database():
    with app.app_context(): 
        db.create_all()
        
        if not Subject.query.first():
            subjects = ['Matematika', 'Fizika', 'Kimyo', 'Biologiya', 'Informatika va AT', 'Ona tili', 'Ingliz tili']
            for subject in subjects:
                db.session.add(Subject(name=subject))
            
            quarters = [
                ('1-chorak', 1),
                ('2-chorak', 2), 
                ('3-chorak', 3),
                ('4-chorak', 4)
            ]
            for name, order in quarters:
                db.session.add(Quarter(name=name, order_num=order))
            
            exam_names = ['BSB-1', 'BSB-2', 'CHSB-1', 'CHSB-2', 'Loyiha ishi']
            for name in exam_names:
                db.session.add(ExamName(name=name))
            
            exam_types = ['Amaliy', 'Nazariy', 'Oraliq', 'Yakuniy']
            for name in exam_types:
                db.session.add(ExamType(name=name))
            
            question_types = [
                'Test', "To'ldirish", 'Qisqa javob',
                'Moslashtirish', 'Masala', 'Tahlil',
            ]
            for name in question_types:
                db.session.add(QuestionType(name=name))
            
            staff_titles = ['O\'qituvchi', 'Maktab direktori', 'O\'quv ishlari bo\'yicha direktor o\'rinbosari']
            for title in staff_titles:
                db.session.add(StaffTitle(title=title))
        
        admin = Employee.query.filter_by(username='admin').first()
        if not admin:
            admin = Employee(
                username='admin',
                first_name='Admin',
                last_name='User',
                is_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
        
        db.session.commit()
        print('Ma\'lumotlar bazasi tayyor!')
        print('Admin login: admin')
        print('Admin parol: admin123')

if __name__ == '__main__':
    init_database()
