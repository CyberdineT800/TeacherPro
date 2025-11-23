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
    """Excel hisobot yaratish - example.docx formatiga mos (async)"""
    output = BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Natijalar"
    
    # Sarlavha qismi
    header_lines = exam_data['header'].split('\n')
    current_row = 1
    
    # Savollar sonini olish
    students = exam_data['students']
    question_count = 0
    if students:
        question_count = len([k for k in students[0].keys() if k.startswith('Savol ')])
    
    # Umumiy ustunlar soni: T/R + F.I.Sh + Questions + Jami + %
    total_cols = 2 + question_count + 2
    last_col = openpyxl.utils.get_column_letter(total_cols)
    
    for line in header_lines:
        ws.merge_cells(f'A{current_row}:{last_col}{current_row}')
        cell = ws[f'A{current_row}']
        cell.value = line
        cell.font = openpyxl.styles.Font(bold=True, size=12)
        cell.alignment = openpyxl.styles.Alignment(horizontal='center', vertical='center')
        current_row += 1
    
    # Sana qo'shish
    if 'date' in exam_data and exam_data['date']:
        ws.merge_cells(f'A{current_row}:{last_col}{current_row}')
        cell = ws[f'A{current_row}']
        cell.value = f"Sana: {exam_data['date']}"
        cell.font = openpyxl.styles.Font(bold=True, size=11)
        cell.alignment = openpyxl.styles.Alignment(horizontal='center', vertical='center')
        current_row += 1
    
    # Bo'sh qator
    current_row += 1
    
    # Jadval sarlavhasi
    headers = ['T/R', "O'quvchilar F. I. Sh"]
    
    # Savol ustunlari
    for i in range(1, question_count + 1):
        headers.append(str(i))
    
    headers.extend(['Jami', '%'])
    
    # Sarlavhalarni yozish
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=current_row, column=col_idx)
        cell.value = header
        cell.font = openpyxl.styles.Font(bold=True, size=11)
        cell.alignment = openpyxl.styles.Alignment(horizontal='center', vertical='center')
        cell.fill = openpyxl.styles.PatternFill(start_color='D9D9D9', end_color='D9D9D9', fill_type='solid')
        cell.border = openpyxl.styles.Border(
            left=openpyxl.styles.Side(style='thin'),
            right=openpyxl.styles.Side(style='thin'),
            top=openpyxl.styles.Side(style='thin'),
            bottom=openpyxl.styles.Side(style='thin')
        )
    
    current_row += 1
    
    # Guruhlar bo'yicha o'quvchilarni tartiblash
    students_by_group = {}
    for student in students:
        group = student['Guruh']
        if group not in students_by_group:
            students_by_group[group] = []
        students_by_group[group].append(student)
    
    # O'quvchilar ma'lumotlarini yozish
    student_number = 1
    for group_num in sorted(students_by_group.keys()):
        # Guruh sarlavhasi
        ws.merge_cells(f'A{current_row}:{last_col}{current_row}')
        cell = ws[f'A{current_row}']
        cell.value = f"{group_num}-guruh"
        cell.font = openpyxl.styles.Font(bold=True, size=11)
        cell.alignment = openpyxl.styles.Alignment(horizontal='left', vertical='center')
        cell.fill = openpyxl.styles.PatternFill(start_color='E7E6E6', end_color='E7E6E6', fill_type='solid')
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
            cell.alignment = openpyxl.styles.Alignment(horizontal='left', vertical='center')
            col_idx += 1
            
            # Savol ballari
            for i in range(1, question_count + 1):
                cell = ws.cell(row=current_row, column=col_idx)
                score = student.get(f'Savol {i}', 0)
                cell.value = score
                cell.font = openpyxl.styles.Font(bold=True)
                cell.alignment = openpyxl.styles.Alignment(horizontal='center', vertical='center')
                col_idx += 1
            
            # Jami ball
            cell = ws.cell(row=current_row, column=col_idx)
            cell.value = student['Jami ball']
            cell.font = openpyxl.styles.Font(bold=True)
            cell.alignment = openpyxl.styles.Alignment(horizontal='center', vertical='center')
            col_idx += 1
            
            # Foiz
            cell = ws.cell(row=current_row, column=col_idx)
            cell.value = student['Foiz']
            cell.font = openpyxl.styles.Font(bold=True)
            cell.alignment = openpyxl.styles.Alignment(horizontal='center', vertical='center')
            
            # Qator chegaralari
            for c in range(1, col_idx + 1):
                ws.cell(row=current_row, column=c).border = openpyxl.styles.Border(
                    left=openpyxl.styles.Side(style='thin'),
                    right=openpyxl.styles.Side(style='thin'),
                    top=openpyxl.styles.Side(style='thin'),
                    bottom=openpyxl.styles.Side(style='thin')
                )
            
            current_row += 1
            student_number += 1
    
    # Bo'sh qatorlar
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
        
        current_row += 1
    
    # Ustun kengliklarini sozlash
    ws.column_dimensions['A'].width = 6  # T/R
    ws.column_dimensions['B'].width = 35  # F.I.Sh
    
    # Savol ustunlari
    for i in range(question_count):
        col_letter = openpyxl.utils.get_column_letter(3 + i)
        ws.column_dimensions[col_letter].width = 8
    
    # Jami va % ustunlari
    jami_col = openpyxl.utils.get_column_letter(3 + question_count)
    percent_col = openpyxl.utils.get_column_letter(4 + question_count)
    ws.column_dimensions[jami_col].width = 10
    ws.column_dimensions[percent_col].width = 10
    
    wb.save(output)
    output.seek(0)
    return output

async def generate_pdf_report(exam_data):
    """PDF hisobot yaratish - example.docx formatiga mos (async)"""
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
    
    # Sarlavha
    header_lines = exam_data['header'].split('\n')
    for line in header_lines:
        title = Paragraph(line, title_style)
        elements.append(title)
    
    # Sana qo'shish
    if 'date' in exam_data and exam_data['date']:
        date_style = ParagraphStyle(
            'DateStyle',
            parent=styles['Normal'],
            alignment=TA_CENTER,
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
        question_count = len([k for k in students[0].keys() if k.startswith('Savol ')])
        
        # Sarlavha qatori
        headers = ['T/R', "O'quvchilar F. I. Sh"]
        for i in range(1, question_count + 1):
            headers.append(str(i))
        headers.extend(['Jami', '%'])
        
        data = [headers]
        
        # Guruhlar bo'yicha
        students_by_group = {}
        for student in students:
            group = student['Guruh']
            if group not in students_by_group:
                students_by_group[group] = []
            students_by_group[group].append(student)
        
        student_number = 1
        for group_num in sorted(students_by_group.keys()):
            # Guruh sarlavhasi
            group_row = [f"{group_num}-guruh"] + [''] * (len(headers) - 1)
            data.append(group_row)
            
            # Guruh o'quvchilari
            for student in students_by_group[group_num]:
                row = [
                    str(student_number),
                    f"{student['Familiya']} {student['Ism']}"
                ]
                
                for i in range(1, question_count + 1):
                    row.append(str(student.get(f'Savol {i}', 0)))
                
                row.append(str(student['Jami ball']))
                row.append(student['Foiz'])
                
                data.append(row)
                student_number += 1
        
        # Jadval yaratish - to'g'ri ustun kengliklari
        col_widths = [0.4*inch, 2.5*inch]  # T/R va F.I.Sh
        
        # Savol ustunlari
        for _ in range(question_count):
            col_widths.append(0.4*inch)
        
        # Jami va % ustunlari
        col_widths.extend([0.6*inch, 0.6*inch])
        
        table = Table(data, colWidths=col_widths, repeatRows=1)
        
        # Jadval stili
        table_style = [
            # Sarlavha
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D9D9D9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            
            # Ma'lumotlar
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # T/R ustuni
            ('ALIGN', (2, 1), (-1, -1), 'CENTER'),  # Savol, Jami, % ustunlari
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            
            # Chegaralar
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),
        ]
        
        # Guruh qatorlari uchun stil
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
    """Word hisobot yaratish - example.docx formatiga mos (async)"""
    output = BytesIO()
    doc = Document()
    
    # Sarlavha
    header_lines = exam_data['header'].split('\n')
    for line in header_lines:
        para = doc.add_paragraph(line)
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.runs[0].font.size = Pt(12)
        para.runs[0].font.bold = True
    
    # Sana qo'shish
    if 'date' in exam_data and exam_data['date']:
        date_para = doc.add_paragraph(f"Sana: {exam_data['date']}")
        date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        date_para.runs[0].font.size = Pt(11)
        date_para.runs[0].font.bold = True
    
    doc.add_paragraph()
    
    # Jadval yaratish
    students = exam_data['students']
    if students:
        question_count = len([k for k in students[0].keys() if k.startswith('Savol ')])
        
        # Ustunlar soni: T/R + F.I.Sh + Questions + Jami + %
        col_count = 2 + question_count + 2
        
        table = doc.add_table(rows=1, cols=col_count)
        table.style = 'Table Grid'
        
        # Sarlavha qatori
        headers = ['T/R', "O'quvchilar F. I. Sh"]
        for i in range(1, question_count + 1):
            headers.append(str(i))
        headers.extend(['Jami', '%'])
        
        hdr_cells = table.rows[0].cells
        for idx, header in enumerate(headers):
            hdr_cells[idx].text = header
            hdr_cells[idx].paragraphs[0].runs[0].font.bold = True
            hdr_cells[idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            # Kulrang fon
            shading_elm = OxmlElement('w:shd')
            shading_elm.set(qn('w:fill'), 'D9D9D9')
            hdr_cells[idx]._element.get_or_add_tcPr().append(shading_elm)
        
        # Guruhlar bo'yicha
        students_by_group = {}
        for student in students:
            group = student['Guruh']
            if group not in students_by_group:
                students_by_group[group] = []
            students_by_group[group].append(student)
        
        student_number = 1
        for group_num in sorted(students_by_group.keys()):
            # Guruh sarlavhasi
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
                
                # Savol ballari
                for i in range(1, question_count + 1):
                    score = student.get(f'Savol {i}', 0)
                    row[col_idx].text = str(score)
                    row[col_idx].paragraphs[0].runs[0].font.bold = True
                    row[col_idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                    col_idx += 1
                
                # Jami ball
                row[col_idx].text = str(student['Jami ball'])
                row[col_idx].paragraphs[0].runs[0].font.bold = True
                row[col_idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                col_idx += 1
                
                # Foiz
                row[col_idx].text = student['Foiz']
                row[col_idx].paragraphs[0].runs[0].font.bold = True
                row[col_idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                student_number += 1
        
        # Ustun kengliklarini sozlash
        table.columns[0].width = Inches(0.4)  # T/R
        table.columns[1].width = Inches(2.5)  # F.I.Sh
        
        # Savol ustunlari
        for i in range(2, 2 + question_count):
            table.columns[i].width = Inches(0.4)
        
        # Jami va % ustunlari
        table.columns[2 + question_count].width = Inches(0.6)  # Jami
        table.columns[3 + question_count].width = Inches(0.6)  # %
    
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