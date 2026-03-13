from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

REPORT_DIR = "reports"
os.makedirs(REPORT_DIR, exist_ok=True)

def generate_pdf(filename):
    file_path = f"{REPORT_DIR}/{filename}_report.pdf"
    c = canvas.Canvas(file_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(200, 750, "Resume Analysis Report")
    c.setFont("Helvetica", 12)
    c.drawString(50, 700, f"Resume: {filename}")
    c.drawString(50, 680, "Report generated successfully!")
    c.save()
    return file_path