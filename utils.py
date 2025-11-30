import openpyxl
import pandas as pd
from io import BytesIO
from docx import Document
from reportlab.lib import colors
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from fastapi import UploadFile

async def process_student_excel(file: UploadFile):
    """
    Excel fayldan o'quvchilar ma'lumotlarini o'qish (async)
    Ism va familiya bitta ustunda "Familiya Ism" formatida
    """
    try:
        # Read file content
        content = await file.read()
        df = pd.read_excel(BytesIO(content))
        df.columns = df.columns.astype(str).str.lower().str.strip()
        
        name_columns = ['name', 'ism', 'f.i.o', 'fio', 'full_name', 'fullname', 'toliq_ism', 'toliq ism', 'familiya ism', 'familiya_ism', 'oâ€˜quvchilar f. i. sh']
        gender_columns = ['gender', 'jins', 'sex', 'jinsi']
        group_columns = ['group', 'guruh', 'group_number', 'groupnumber', 'guruhi']
        
        name_col = None
        gender_col = None
        group_col = None
        
        for col in df.columns:
            if col in name_columns:
                name_col = col
            elif col in gender_columns:
                gender_col = col
            elif col in group_columns:
                group_col = col
        
        if name_col is None and len(df.columns) > 0:
            name_col = df.columns[0]
        
        students = []
        has_group = group_col is not None
        
        for idx, row in df.iterrows():
            try:
                if name_col and name_col in df.columns:
                    full_name = str(row[name_col]).strip()
                    name_parts = full_name.split()
                    
                    if len(name_parts) >= 2:
                        last_name = ' '.join(name_parts[:-1]).strip()
                        first_name = name_parts[-1].strip()
                    else:
                        last_name = full_name
                        first_name = f"O'quvchi_{idx+1}"
                else:
                    first_name = f"O'quvchi_{idx+1}"
                    last_name = ""
                
                if gender_col and gender_col in df.columns:
                    gender_val = str(row[gender_col]).strip()
                    try:
                        if gender_val.isdigit():
                            gender = int(gender_val)
                        elif gender_val.lower() in ['erkak', 'male', 'e', 'm', '1', 'o\'g\'il']:
                            gender = 1
                        elif gender_val.lower() in ['ayol', 'female', 'a', 'f', '2', 'qiz']:
                            gender = 2
                        else:
                            gender = 1
                    except:
                        gender = 1
                else:
                    gender = 1
                
                if has_group and group_col in df.columns:
                    group_val = str(row[group_col]).strip()
                    try:
                        if group_val.isdigit():
                            group = int(group_val)
                        else:
                            group = 1
                    except:
                        group = 1
                else:
                    group = 1 if idx < len(df) // 2 else 2
                
                group = max(1, min(2, group))
                
                students.append({
                    'first_name': first_name,
                    'last_name': last_name,
                    'gender': gender,
                    'group_number': group
                })
                
            except Exception as e:
                print(f"Qator {idx+1} ni qayta ishlashda xatolik: {e}")
                continue
        
        print(f"Excel fayldan {len(students)} ta o'quvchi yuklandi")
        return students
        
    except Exception as e:
        print(f"Excel faylni o'qishda xatolik: {e}")
        return []

async def generate_excel_report(exam_data):
    """Excel hisobot yaratish - yangilangan format PDF ga o'xshash ko'rinishda"""
    output = BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Natijalar"
    
    is_bsb = exam_data.get('is_bsb_exam', False)
    is_chsb = exam_data.get('is_chsb_exam', False)
    is_project = exam_data.get('is_project_exam', False)
    show_groups = exam_data.get('show_groups', True)
    
    # Sarlavha qismi
    header_lines = exam_data['header'].split('\n')
    current_row = 1
    
    # Calculate column count based on exam type
    if is_project:
        question_count = 1
    elif is_bsb:
        question_count = 5
    elif is_chsb:
        question_count = len(exam_data.get('question_types_summary', []))
    else:
        students = exam_data['students']
        question_count = len(students[0]['scores']) if students else 0
    
    # Columns: T/R + F.I.Sh + [Variant] + Questions + Jami + %
    base_cols = 3 if not (is_bsb or is_chsb or is_project) else 2
    total_cols = base_cols + question_count + 2
    last_col = openpyxl.utils.get_column_letter(total_cols)
    
    # Set default row height for PDF-like appearance
    ws.sheet_format.defaultRowHeight = 25
    
    for line in header_lines:
        ws.merge_cells(f'A{current_row}:{last_col}{current_row}')
        cell = ws[f'A{current_row}']
        cell.value = line
        cell.font = openpyxl.styles.Font(bold=True, size=14)
        cell.alignment = openpyxl.styles.Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[current_row].height = 30
        current_row += 1
    
    # Sana qo'shish (chapda)
    if 'date' in exam_data and exam_data['date']:
        ws.merge_cells(f'A{current_row}:{last_col}{current_row}')
        cell = ws[f'A{current_row}']
        cell.value = f"Sana: {exam_data['date']}"
        cell.font = openpyxl.styles.Font(bold=True, size=12)
        cell.alignment = openpyxl.styles.Alignment(horizontal='left', vertical='center')
        ws.row_dimensions[current_row].height = 25
        current_row += 1
    
    # Bo'sh qator
    current_row += 1
    ws.row_dimensions[current_row].height = 15
    
    # Jadval sarlavhasi
    headers = ['T/R', "O'quvchilar F. I. Sh"]
    
    # Add Variant column for regular exams
    if not (is_bsb or is_chsb or is_project):
        headers.append('Variant')
    
    # Savol ustunlari
    if is_chsb:
        for qtype in exam_data.get('question_types_summary', []):
            headers.append(qtype['name'])
    elif is_project:
        headers.append('Ball')
    elif is_bsb:
        for i in range(1, 6):
            headers.append(str(i))
    else:
        for i in range(1, question_count + 1):
            headers.append(str(i))
    
    headers.extend(['Jami', '%'])
    
    # Sarlavhalarni yozish
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=current_row, column=col_idx)
        cell.value = header
        cell.font = openpyxl.styles.Font(bold=True, size=11)
        cell.alignment = openpyxl.styles.Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.fill = openpyxl.styles.PatternFill(start_color='D9D9D9', end_color='D9D9D9', fill_type='solid')
        cell.border = openpyxl.styles.Border(
            left=openpyxl.styles.Side(style='thin'),
            right=openpyxl.styles.Side(style='thin'),
            top=openpyxl.styles.Side(style='thin'),
            bottom=openpyxl.styles.Side(style='thin')
        )
    
    ws.row_dimensions[current_row].height = 35
    current_row += 1
    
    # Guruhlar bo'yicha o'quvchilarni tartiblash
    students = exam_data['students']
    students_by_group = {}
    
    if show_groups:
        for student in students:
            group = student.get('Guruh', 1)
            if group not in students_by_group:
                students_by_group[group] = []
            students_by_group[group].append(student)
    else:
        students_by_group[0] = students
    
    # O'quvchilar ma'lumotlarini yozish
    student_number = 1
    
    # Track totals for average calculation
    score_totals = [0.0] * question_count
    jami_total = 0.0
    percentage_total = 0.0
    total_students = len(students)
    
    for group_num in sorted(students_by_group.keys()):
        # Guruh sarlavhasi (faqat show_groups=True bo'lsa)
        if show_groups:
            ws.merge_cells(f'A{current_row}:{last_col}{current_row}')
            cell = ws[f'A{current_row}']
            cell.value = f"{group_num}-guruh"
            cell.font = openpyxl.styles.Font(bold=True, size=11)
            cell.alignment = openpyxl.styles.Alignment(horizontal='left', vertical='center')
            cell.fill = openpyxl.styles.PatternFill(start_color='E7E6E6', end_color='E7E6E6', fill_type='solid')
            ws.row_dimensions[current_row].height = 25
            current_row += 1
        
        # Guruh o'quvchilari
        for student in students_by_group[group_num]:
            col_idx = 1
            
            # T/R
            cell = ws.cell(row=current_row, column=col_idx)
            cell.value = student_number
            cell.font = openpyxl.styles.Font(bold=True)
            cell.alignment = openpyxl.styles.Alignment(horizontal='center', vertical='center')
            col_idx += 1
            
            # F.I.Sh
            cell = ws.cell(row=current_row, column=col_idx)
            cell.value = f"{student['Familiya']} {student['Ism']}"
            cell.alignment = openpyxl.styles.Alignment(horizontal='left', vertical='center', wrap_text=True)
            col_idx += 1
            
            # Variant (faqat oddiy imtihonlar uchun)
            if not (is_bsb or is_chsb or is_project):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.value = exam_data.get('variant', 1)
                cell.font = openpyxl.styles.Font(bold=True)
                cell.alignment = openpyxl.styles.Alignment(horizontal='center', vertical='center')
                col_idx += 1
            
            # Savol ballari
            for idx, score in enumerate(student['scores']):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.value = score
                cell.font = openpyxl.styles.Font(bold=True)
                cell.alignment = openpyxl.styles.Alignment(horizontal='center', vertical='center')
                score_totals[idx] += score
                col_idx += 1
            
            # Jami ball
            cell = ws.cell(row=current_row, column=col_idx)
            cell.value = student['Jami ball']
            cell.font = openpyxl.styles.Font(bold=True)
            cell.alignment = openpyxl.styles.Alignment(horizontal='center', vertical='center')
            jami_total += student['Jami ball']
            col_idx += 1
            
            # Foiz
            cell = ws.cell(row=current_row, column=col_idx)
            cell.value = student['Foiz']
            cell.font = openpyxl.styles.Font(bold=True)
            cell.alignment = openpyxl.styles.Alignment(horizontal='center', vertical='center')
            percentage_value = float(student['Foiz'].rstrip('%'))
            percentage_total += percentage_value
            
            # Qator chegaralari
            for c in range(1, col_idx + 1):
                ws.cell(row=current_row, column=c).border = openpyxl.styles.Border(
                    left=openpyxl.styles.Side(style='thin'),
                    right=openpyxl.styles.Side(style='thin'),
                    top=openpyxl.styles.Side(style='thin'),
                    bottom=openpyxl.styles.Side(style='thin')
                )
            
            ws.row_dimensions[current_row].height = 25
            current_row += 1
            student_number += 1
    
    # O'rtacha qiymatlar qatori
    col_idx = 1
    
    # T/R (bo'sh)
    cell = ws.cell(row=current_row, column=col_idx)
    cell.value = ""
    col_idx += 1
    
    # F.I.Sh -> "O'rtacha"
    cell = ws.cell(row=current_row, column=col_idx)
    cell.value = "O'rtacha"
    cell.font = openpyxl.styles.Font(bold=True, size=11)
    cell.alignment = openpyxl.styles.Alignment(horizontal='left', vertical='center')
    cell.fill = openpyxl.styles.PatternFill(start_color='FFD966', end_color='FFD966', fill_type='solid')
    col_idx += 1
    
    # Variant (bo'sh, faqat oddiy imtihonlar uchun)
    if not (is_bsb or is_chsb or is_project):
        cell = ws.cell(row=current_row, column=col_idx)
        cell.value = ""
        col_idx += 1
    
    # O'rtacha ballar
    for avg_score in score_totals:
        cell = ws.cell(row=current_row, column=col_idx)
        cell.value = round(avg_score / total_students, 2) if total_students > 0 else 0
        cell.font = openpyxl.styles.Font(bold=True)
        cell.alignment = openpyxl.styles.Alignment(horizontal='center', vertical='center')
        cell.fill = openpyxl.styles.PatternFill(start_color='FFD966', end_color='FFD966', fill_type='solid')
        col_idx += 1
    
    # O'rtacha jami
    cell = ws.cell(row=current_row, column=col_idx)
    cell.value = round(jami_total / total_students, 2) if total_students > 0 else 0
    cell.font = openpyxl.styles.Font(bold=True)
    cell.alignment = openpyxl.styles.Alignment(horizontal='center', vertical='center')
    cell.fill = openpyxl.styles.PatternFill(start_color='FFD966', end_color='FFD966', fill_type='solid')
    col_idx += 1
    
    # O'rtacha foiz
    cell = ws.cell(row=current_row, column=col_idx)
    avg_percentage = round(percentage_total / total_students, 1) if total_students > 0 else 0
    cell.value = f"{avg_percentage}%"
    cell.font = openpyxl.styles.Font(bold=True)
    cell.alignment = openpyxl.styles.Alignment(horizontal='center', vertical='center')
    cell.fill = openpyxl.styles.PatternFill(start_color='FFD966', end_color='FFD966', fill_type='solid')
    
    # O'rtacha qator chegaralari
    for c in range(1, col_idx + 1):
        ws.cell(row=current_row, column=c).border = openpyxl.styles.Border(
            left=openpyxl.styles.Side(style='thin'),
            right=openpyxl.styles.Side(style='thin'),
            top=openpyxl.styles.Side(style='medium'),
            bottom=openpyxl.styles.Side(style='medium')
        )
    
    ws.row_dimensions[current_row].height = 30
    current_row += 2
    
    # Footer ma'lumotlari
    footer_data = [
        ("Fan o'qituvchisi :", exam_data['teacher']),
        ("O'IBDO':", ""),
        ("M/b raisi:", "")
    ]
    
    for label, value in footer_data:
        ws.merge_cells(f'A{current_row}:B{current_row}')
        cell = ws[f'A{current_row}']
        cell.value = label
        cell.font = openpyxl.styles.Font(bold=True)
        cell.alignment = openpyxl.styles.Alignment(horizontal='left', vertical='center')
        
        ws.merge_cells(f'C{current_row}:{last_col}{current_row}')
        cell = ws[f'C{current_row}']
        cell.value = value
        cell.font = openpyxl.styles.Font(bold=True)
        cell.alignment = openpyxl.styles.Alignment(horizontal='left', vertical='center')
        
        ws.row_dimensions[current_row].height = 25
        current_row += 1

    # FIXED COLUMN WIDTH SETTINGS - Manual approach without auto_adjust
    # Using direct width settings that work reliably
    
    # T/R column
    ws.column_dimensions['A'].width = 8
    
    # F.I.Sh column - this should now work correctly
    ws.column_dimensions['B'].width = 30
    
    # Variant column if exists
    if not (is_bsb or is_chsb or is_project):
        ws.column_dimensions['C'].width = 10
    
    # Question columns
    start_col_idx = 3 if not (is_bsb or is_chsb or is_project) else 2
    
    for i in range(question_count):
        col_letter = openpyxl.utils.get_column_letter(start_col_idx + i + (1 if not (is_bsb or is_chsb or is_project) else 0))
        if is_chsb:
            ws.column_dimensions[col_letter].width = 12
        elif is_project:
            ws.column_dimensions[col_letter].width = 12
        else:
            ws.column_dimensions[col_letter].width = 10
    
    # Jami and % columns
    jami_col = openpyxl.utils.get_column_letter(total_cols - 1)
    percent_col = openpyxl.utils.get_column_letter(total_cols)
    ws.column_dimensions[jami_col].width = 12
    ws.column_dimensions[percent_col].width = 12

    # Alternative: Simple auto-width function that handles merged cells
    def safe_auto_adjust_columns(worksheet):
        for col_idx in range(1, worksheet.max_column + 1):
            col_letter = openpyxl.utils.get_column_letter(col_idx)
            max_length = 0
            
            # Check each cell in the column
            for row_idx in range(1, worksheet.max_row + 1):
                try:
                    cell = worksheet.cell(row=row_idx, column=col_idx)
                    # Skip if cell is part of a merge
                    if any(cell.coordinate in merge for merge in worksheet.merged_cells.ranges):
                        continue
                    
                    if cell.value:
                        length = len(str(cell.value))
                        if length > max_length:
                            max_length = length
                except:
                    continue
            
            # Set width with some padding
            if max_length > 0:
                worksheet.column_dimensions[col_letter].width = min(max_length + 2, 50)
    
    # Apply safe auto-adjust if needed (optional)
    # safe_auto_adjust_columns(ws)
    
    # Ensure F.I.Sh column has the desired width
    ws.column_dimensions['B'].width = 30
    
    # Matn o'ralishini yoqish
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                cell.alignment = openpyxl.styles.Alignment(
                    horizontal=cell.alignment.horizontal,
                    vertical='center',
                    wrap_text=True
                )
    
    # Print settings
    ws.print_area = f'A1:{last_col}{current_row-1}'
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE if total_cols > 8 else ws.ORIENTATION_PORTRAIT
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToHeight = 0
    ws.page_setup.fitToWidth = 1
    
    wb.save(output)
    output.seek(0)
    return output

async def generate_pdf_report(exam_data):
    """PDF hisobot yaratish - yangilangan format"""
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        spaceAfter=20,
        fontSize=12,
        fontName='Helvetica-Bold'
    )
    
    is_bsb = exam_data.get('is_bsb_exam', False)
    is_chsb = exam_data.get('is_chsb_exam', False)
    is_project = exam_data.get('is_project_exam', False)
    show_groups = exam_data.get('show_groups', True)
    
    # Sarlavha
    header_lines = exam_data['header'].split('\n')
    for line in header_lines:
        title = Paragraph(line, title_style)
        elements.append(title)
    
    # Sana qo'shish (chapda)
    if 'date' in exam_data and exam_data['date']:
        date_style = ParagraphStyle(
            'DateStyle',
            parent=styles['Normal'],
            alignment=0,  # Left alignment
            spaceAfter=15,
            fontSize=11,
            fontName='Helvetica-Bold'
        )
        date_text = Paragraph(f"Sana: {exam_data['date']}", date_style)
        elements.append(date_text)
    
    elements.append(Spacer(1, 0.2*inch))
    
    # Jadval yaratish
    students = exam_data['students']
    if students:
        if is_project:
            question_count = 1
        elif is_bsb:
            question_count = 5
        elif is_chsb:
            question_count = len(exam_data.get('question_types_summary', []))
        else:
            question_count = len(students[0]['scores'])
        
        # Sarlavha qatori
        headers = ['T/R', "O'quvchilar F. I. Sh"]
        
        if not (is_bsb or is_chsb or is_project):
            headers.append('Variant')
        
        if is_chsb:
            for qtype in exam_data.get('question_types_summary', []):
                headers.append(qtype['name'])
        elif is_project:
            headers.append('Ball')
        elif is_bsb:
            for i in range(1, 6):
                headers.append(str(i))
        else:
            for i in range(1, question_count + 1):
                headers.append(str(i))
        
        headers.extend(['Jami', '%'])
        
        data = [headers]
        
        # Guruhlar bo'yicha
        students_by_group = {}
        if show_groups:
            for student in students:
                group = student.get('Guruh', 1)
                if group not in students_by_group:
                    students_by_group[group] = []
                students_by_group[group].append(student)
        else:
            students_by_group[0] = students
        
        student_number = 1
        
        # Track totals
        score_totals = [0.0] * question_count
        jami_total = 0.0
        percentage_total = 0.0
        total_students = len(students)
        
        for group_num in sorted(students_by_group.keys()):
            # Guruh sarlavhasi
            if show_groups:
                group_row = [f"{group_num}-guruh"] + [''] * (len(headers) - 1)
                data.append(group_row)
            
            # Guruh o'quvchilari
            for student in students_by_group[group_num]:
                row = [
                    str(student_number),
                    f"{student['Familiya']} {student['Ism']}"
                ]
                
                if not (is_bsb or is_chsb or is_project):
                    row.append(str(exam_data.get('variant', 1)))
                
                for idx, score in enumerate(student['scores']):
                    row.append(str(round(score, 1)))
                    score_totals[idx] += score
                
                row.append(str(round(student['Jami ball'], 1)))
                row.append(student['Foiz'])
                
                jami_total += student['Jami ball']
                percentage_value = float(student['Foiz'].rstrip('%'))
                percentage_total += percentage_value
                
                data.append(row)
                student_number += 1
        
        # O'rtacha qatori
        avg_row = ['', "O'rtacha"]
        
        if not (is_bsb or is_chsb or is_project):
            avg_row.append('')
        
        for avg_score in score_totals:
            avg_row.append(str(round(avg_score / total_students, 2)) if total_students > 0 else '0')
        
        avg_row.append(str(round(jami_total / total_students, 2)) if total_students > 0 else '0')
        avg_percentage = round(percentage_total / total_students, 1) if total_students > 0 else 0
        avg_row.append(f"{avg_percentage}%")
        
        data.append(avg_row)
        
        # Jadval yaratish
        col_widths = [0.4*inch, 2.5*inch]
        
        if not (is_bsb or is_chsb or is_project):
            col_widths.append(0.5*inch)
        
        for _ in range(question_count):
            if is_chsb:
                col_widths.append(0.6*inch)
            else:
                col_widths.append(0.4*inch)
        
        col_widths.extend([0.6*inch, 0.6*inch])
        
        table = Table(data, colWidths=col_widths, repeatRows=1)
        
        # Jadval stili
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D9D9D9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),
            ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FFD966')),
            ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.black),
        ]
        
        # Guruh qatorlari uchun stil
        if show_groups:
            row_idx = 1
            for group_num in sorted(students_by_group.keys()):
                table_style.append(('SPAN', (0, row_idx), (-1, row_idx)))
                table_style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#E7E6E6')))
                table_style.append(('ALIGN', (0, row_idx), (-1, row_idx), 'LEFT'))
                row_idx += len(students_by_group[group_num]) + 1
        
        table.setStyle(TableStyle(table_style))
        elements.append(table)
        elements.append(Spacer(1, 0.3*inch))
    
    # Footer
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold')
    elements.append(Paragraph(f"<b>Fan o'qituvchisi:</b> {exam_data['teacher']}", footer_style))
    
    doc.build(elements)
    output.seek(0)
    return output

def set_cell_border(cell, **kwargs):
    """Word jadval katagi chegaralarini sozlash"""
    tc = cell._element
    tcPr = tc.get_or_add_tcPr()
    
    tcBorders = OxmlElement('w:tcBorders')
    for edge in ('top', 'left', 'bottom', 'right'):
        if edge in kwargs:
            edge_data = kwargs.get(edge)
            edge_el = OxmlElement(f'w:{edge}')
            edge_el.set(qn('w:val'), 'single')
            edge_el.set(qn('w:sz'), str(edge_data.get('sz', 4)))
            edge_el.set(qn('w:space'), '0')
            edge_el.set(qn('w:color'), edge_data.get('color', '000000'))
            tcBorders.append(edge_el)
    tcPr.append(tcBorders)

async def generate_word_report(exam_data):
    """Word hisobot yaratish - yangilangan format"""
    output = BytesIO()
    doc = Document()
    
    is_bsb = exam_data.get('is_bsb_exam', False)
    is_chsb = exam_data.get('is_chsb_exam', False)
    is_project = exam_data.get('is_project_exam', False)
    show_groups = exam_data.get('show_groups', True)
    
    # Sarlavha
    header_lines = exam_data['header'].split('\n')
    for line in header_lines:
        para = doc.add_paragraph(line)
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.runs[0].font.size = Pt(12)
        para.runs[0].font.bold = True
    
    # Sana qo'shish (chapda)
    if 'date' in exam_data and exam_data['date']:
        date_para = doc.add_paragraph(f"Sana: {exam_data['date']}")
        date_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
        date_para.runs[0].font.size = Pt(11)
        date_para.runs[0].font.bold = True
        doc.add_paragraph()

    # Jadval yaratish
    students = exam_data['students']
    if students:
        if is_project:
            question_count = 1
        elif is_bsb:
            question_count = 5
        elif is_chsb:
            question_count = len(exam_data.get('question_types_summary', []))
        else:
            question_count = len(students[0]['scores'])
        
        # Ustunlar soni
        base_cols = 3 if not (is_bsb or is_chsb or is_project) else 2
        col_count = base_cols + question_count + 2
        
        table = doc.add_table(rows=1, cols=col_count)
        table.style = 'Table Grid'
        
        # Sarlavha qatori
        headers = ['T/R', "O'quvchilar F. I. Sh"]
        
        if not (is_bsb or is_chsb or is_project):
            headers.append('Variant')
        
        if is_chsb:
            for qtype in exam_data.get('question_types_summary', []):
                headers.append(qtype['name'])
        elif is_project:
            headers.append('Ball')
        elif is_bsb:
            for i in range(1, 6):
                headers.append(str(i))
        else:
            for i in range(1, question_count + 1):
                headers.append(str(i))
        
        headers.extend(['Jami', '%'])
        
        hdr_cells = table.rows[0].cells
        for idx, header in enumerate(headers):
            hdr_cells[idx].text = header
            hdr_cells[idx].paragraphs[0].runs[0].font.bold = True
            hdr_cells[idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            shading_elm = OxmlElement('w:shd')
            shading_elm.set(qn('w:fill'), 'D9D9D9')
            hdr_cells[idx]._element.get_or_add_tcPr().append(shading_elm)
        
        # Guruhlar bo'yicha
        students_by_group = {}
        if show_groups:
            for student in students:
                group = student.get('Guruh', 1)
                if group not in students_by_group:
                    students_by_group[group] = []
                students_by_group[group].append(student)
        else:
            students_by_group[0] = students
        
        student_number = 1
        
        # Track totals
        score_totals = [0.0] * question_count
        jami_total = 0.0
        percentage_total = 0.0
        total_students = len(students)
        
        for group_num in sorted(students_by_group.keys()):
            # Guruh sarlavhasi
            if show_groups:
                row = table.add_row()
                row.cells[0].merge(row.cells[-1])
                row.cells[0].text = f"{group_num}-guruh"
                row.cells[0].paragraphs[0].runs[0].font.bold = True
                shading_elm = OxmlElement('w:shd')
                shading_elm.set(qn('w:fill'), 'E7E6E6')
                row.cells[0]._element.get_or_add_tcPr().append(shading_elm)
            
            # Guruh o'quvchilari
            for student in students_by_group[group_num]:
                row = table.add_row().cells
                
                col_idx = 0
                
                # T/R
                row[col_idx].text = str(student_number)
                row[col_idx].paragraphs[0].runs[0].font.bold = True
                row[col_idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                col_idx += 1
                
                # F.I.Sh
                row[col_idx].text = f"{student['Familiya']} {student['Ism']}"
                row[col_idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
                col_idx += 1
                
                # Variant
                if not (is_bsb or is_chsb or is_project):
                    row[col_idx].text = str(exam_data.get('variant', 1))
                    row[col_idx].paragraphs[0].runs[0].font.bold = True
                    row[col_idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                    col_idx += 1
                
                # Savol ballari
                for idx, score in enumerate(student['scores']):
                    row[col_idx].text = str(round(score, 1))
                    row[col_idx].paragraphs[0].runs[0].font.bold = True
                    row[col_idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                    score_totals[idx] += score
                    col_idx += 1
                
                # Jami ball
                row[col_idx].text = str(round(student['Jami ball'], 1))
                row[col_idx].paragraphs[0].runs[0].font.bold = True
                row[col_idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                jami_total += student['Jami ball']
                col_idx += 1
                
                # Foiz
                row[col_idx].text = student['Foiz']
                row[col_idx].paragraphs[0].runs[0].font.bold = True
                row[col_idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                percentage_value = float(student['Foiz'].rstrip('%'))
                percentage_total += percentage_value
                
                student_number += 1
        
        # O'rtacha qatori
        row = table.add_row().cells
        col_idx = 0
        
        # T/R (bo'sh)
        row[col_idx].text = ""
        col_idx += 1
        
        # F.I.Sh -> "O'rtacha"
        row[col_idx].text = "O'rtacha"
        row[col_idx].paragraphs[0].runs[0].font.bold = True
        row[col_idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
        shading_elm = OxmlElement('w:shd')
        shading_elm.set(qn('w:fill'), 'FFD966')
        row[col_idx]._element.get_or_add_tcPr().append(shading_elm)
        col_idx += 1
        
        # Variant (bo'sh)
        if not (is_bsb or is_chsb or is_project):
            row[col_idx].text = ""
            shading_elm = OxmlElement('w:shd')
            shading_elm.set(qn('w:fill'), 'FFD966')
            row[col_idx]._element.get_or_add_tcPr().append(shading_elm)
            col_idx += 1
        
        # O'rtacha ballar
        for avg_score in score_totals:
            row[col_idx].text = str(round(avg_score / total_students, 2)) if total_students > 0 else '0'
            row[col_idx].paragraphs[0].runs[0].font.bold = True
            row[col_idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            shading_elm = OxmlElement('w:shd')
            shading_elm.set(qn('w:fill'), 'FFD966')
            row[col_idx]._element.get_or_add_tcPr().append(shading_elm)
            col_idx += 1
        
        # O'rtacha jami
        row[col_idx].text = str(round(jami_total / total_students, 2)) if total_students > 0 else '0'
        row[col_idx].paragraphs[0].runs[0].font.bold = True
        row[col_idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        shading_elm = OxmlElement('w:shd')
        shading_elm.set(qn('w:fill'), 'FFD966')
        row[col_idx]._element.get_or_add_tcPr().append(shading_elm)
        col_idx += 1
        
        # O'rtacha foiz
        avg_percentage = round(percentage_total / total_students, 1) if total_students > 0 else 0
        row[col_idx].text = f"{avg_percentage}%"
        row[col_idx].paragraphs[0].runs[0].font.bold = True
        row[col_idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        shading_elm = OxmlElement('w:shd')
        shading_elm.set(qn('w:fill'), 'FFD966')
        row[col_idx]._element.get_or_add_tcPr().append(shading_elm)
        
        # Ustun kengliklarini sozlash
        table.columns[0].width = Inches(0.4)
        table.columns[1].width = Inches(2.5)
        
        start_idx = 3 if not (is_bsb or is_chsb or is_project) else 2
        if not (is_bsb or is_chsb or is_project):
            table.columns[2].width = Inches(0.5)
        
        for i in range(question_count):
            if is_chsb:
                table.columns[start_idx + i].width = Inches(0.6)
            else:
                table.columns[start_idx + i].width = Inches(0.4)
        
        table.columns[col_count - 2].width = Inches(0.6)
        table.columns[col_count - 1].width = Inches(0.6)

    doc.add_paragraph()
    doc.add_paragraph()

    # Footer
    footer_data = [
        ("Fan o'qituvchisi :", exam_data['teacher']),
        ("O'IBDO':", ""),
        ("M/b raisi:", "")
    ]

    for label, value in footer_data:
        para = doc.add_paragraph()
        run1 = para.add_run(label)
        run1.font.bold = True
        run2 = para.add_run(f" {value}")
        run2.font.bold = True

    doc.save(output)
    output.seek(0)
    return output