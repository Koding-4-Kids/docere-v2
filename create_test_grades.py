"""Create test_grades.xlsx with intentional errors for gradebook sync testing."""
import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "CS101 Grades"

# Row 1: Merged title
ws.merge_cells("A1:F1")
ws["A1"] = "Intro to Computer Science - Fall 2026 Grades"
ws["A1"].font = Font(size=14, bold=True)
ws["A1"].alignment = Alignment(horizontal="center")

# Row 2: Empty spacer (just skip it)

# Row 3: Headers
headers = [
    "Student Name",
    "Assignment 1: Variables and Data Types",
    "Assignment 2: Loops and Conditionals",
    "Intro to Data Review",
    "Data Types/ Database",
    "Attendance",
]
for i, h in enumerate(headers, 1):
    ws.cell(row=3, column=i, value=h).font = Font(bold=True)

# Data rows (starting at row 4)
# Moodle students: Sarah Johnson (4), Marcus Chen (5), Priya Patel (6),
# Jordan Williams (7), Emily Rodriguez (8), David Kim (9),
# Aisha Mohammed (10), Tyler Brooks (11)
data = [
    # Normal valid rows
    ["Sarah Johnson",    "85",      "92",      "78",     "88",      "Present"],     # "Present" = format error
    ["Marcus Chen",      "90",      "88",      "95",     "91",      "45"],          # valid
    ["Priya Patel",      "78",      "105",     "82",     "76",      "40"],          # 105 exceeds max (100)
    ["jordan williams",  "88",      "76",      "90",     "84",      "Absent"],      # lowercase name + "Absent"
    ["Emily Rodriguez",  "92",      "",        "87",     "93",      "50"],          # missing grade (empty)
    ["David Kim",        "B+",      "79",      "81",     "85",      "48"],          # "B+" letter grade
    ["Aisha Mohammed",   "-5",      "83",      "91",     "89",      "42"],          # negative grade
    ["Tyler Brooks",     "76",      "84",      "73",     "80",      "38"],          # valid
    ["Ghost Student",    "95",      "87",      "80",     "92",      "50"],          # not enrolled
    ["",                 "",        "",        "",       "",        ""],             # empty row
    ["Sarah Johnson",    "86",      "93",      "79",     "89",      "48"],          # duplicate student
    ["Marcus Chen",      "85/100",  "90",      "88",     "92",      "44"],          # fraction format
]

for row_data in data:
    ws.append(row_data)

# Auto-width columns
for i in range(1, len(headers) + 1):
    ws.column_dimensions[get_column_letter(i)].width = 20

wb.save("test_grades.xlsx")
print("Created test_grades.xlsx")
