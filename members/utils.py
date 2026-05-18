import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter
from django.http import HttpResponse

def generate_migration_template_http() -> HttpResponse:
    """
    Constructs a pristine openpyxl spreadsheet buffer loaded with standard headers,
    color-coded required metrics, instructions, and data validations.
    """
    wb = openpyxl.Workbook()
    
    # Setup Worksheet 1: Data Matrix Canvas
    ws = wb.active
    ws.title = "Data Migration Upload"
    ws.views.sheetView[0].showGridLines = True

    # Typography & Aesthetics Color Palettes
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    instruct_font = Font(name="Segoe UI", size=10, italic=True, color="333333")
    
    required_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid") # Dark Navy Blue (Core Fields)
    optional_fill = PatternFill(start_color="5B9BD5", end_color="5B9BD5", fill_type="solid") # Steel Blue (Optional Profiles)
    
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    # 1. Document Instructions Setup (Merged cleanly across columns A to Z)
    ws.append(["INSTRUCTIONS: Fill out mandatory columns safely. Do not alter column placements or headers. Format dates as YYYY-MM-DD. Leave loan fields empty for members without active balances."])
    ws.merge_cells("A1:Z1")
    
    # Style instruction banner cell
    instruct_cell = ws.cell(row=1, column=1)
    instruct_cell.font = instruct_font
    instruct_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 30

    # 2. Schema Blueprint Definition Matrix (All 26 fields now including guarantor fields)
    headers = [
        # Member Personal Profiles
        ('member_number', required_fill), 
        ('first_name', required_fill), 
        ('last_name', required_fill),
        ('gender', required_fill), 
        ('date_of_birth', required_fill), 
        ('nin', required_fill),
        ('card_number', optional_fill), 
        ('phone_number', required_fill), 
        ('alternative_phone', optional_fill),
        ('email', optional_fill), 
        ('physical_address', optional_fill), 
        ('village', optional_fill),
        ('parish', optional_fill), 
        ('district', optional_fill),
        # Financial Ledger System Balance
        ('savings_balance', required_fill),
        # Active Historical Loan Book Portfolio Tracking
        ('loan_reference', optional_fill), 
        ('principal_amount', optional_fill), 
        ('interest_rate', optional_fill),
        ('period_months', optional_fill), 
        ('loan_start_date', optional_fill), 
        ('principal_balance', optional_fill),
        ('interest_balance', optional_fill), 
        ('product_type', optional_fill), 
        ('loan_purpose', optional_fill),
        ('guarantor_1_name', optional_fill),
        ('guarantor_1_phone', optional_fill)
    ]

    # Write Headers into Row 2
    for col_idx, (header_text, style_fill) in enumerate(headers, start=1):
        cell = ws.cell(row=2, column=col_idx, value=header_text)
        cell.font = header_font
        cell.fill = style_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    
    ws.row_dimensions[2].height = 28

    # 3. Add Hardened Data Validations (Dropdown Selection Constraints)
    gender_dv = DataValidation(type="list", formula1='"Male,Female,Other"', allow_blank=False)
    gender_dv.error = 'Your entry is not in the allowed selection list (Male, Female, Other)'
    gender_dv.errorTitle = 'Invalid Gender Option'
    ws.add_data_validation(gender_dv)
    gender_dv.add("D3:D5000")

    product_dv = DataValidation(type="list", formula1='"personal,business,salary,group,emergency,asset"', allow_blank=True)
    product_dv.error = 'Select a valid product type option'
    product_dv.errorTitle = 'Invalid Product Type'
    ws.add_data_validation(product_dv)
    product_dv.add("W3:W5000")

    # Add descriptive placeholder row to guide data entry clerks
    sample_row = [
        "KAL-001", "John", "Doe", "Male", "1990-05-15", "CM9001234567XX", 
        "CARD-102", "0772000111", "0701000222", "john.doe@email.com", "Kampala Road", 
        "Central Zone", "Nakasero", "Kampala", "250000", "LN-2026-04", "1500000", 
        "12.0", "12", "2025-10-01", "1000000", "120000", "personal", "Business Stock", 
        "Jane Mary Smith", "0772111222"
    ]
    for col_idx, value in enumerate(sample_row, start=1):
        cell = ws.cell(row=3, column=col_idx, value=value)
        cell.border = thin_border
        cell.font = Font(name="Segoe UI", size=10, color="555555")

    # Expand column layouts dynamically 
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or '')) for cell in col[1:])
        ws.column_dimensions[col_letter].width = max(max_len + 4, 15)

    # 4. Stream workbook bytes into memory buffer
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    # 5. Build Outbound Network Payload
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = "attachment; filename=Customer_migration_template.xlsx"
    
    return response