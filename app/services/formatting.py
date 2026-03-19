from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

CLEAN_DIR = "formatted"
os.makedirs(CLEAN_DIR, exist_ok=True)

def compute_format_score(text, summary, skills):
    score = 100
    issues = []

    if not summary.get("summary") or summary.get("summary") == "Profile summary not available":
        score -= 15
        issues.append("Add a concise professional summary.")

    if not summary.get("education") or summary.get("education") == ["Education info not extracted"]:
        score -= 15
        issues.append("Education section is missing or unclear.")

    if not summary.get("experience") or summary.get("experience") == ["Fresher"]:
        score -= 10
        issues.append("Experience section needs more detail.")

    if not skills or len(skills) < 4:
        score -= 15
        issues.append("Add more relevant skills for ATS readability.")

    text_len = len(text or "")
    if text_len < 300:
        score -= 10
        issues.append("Resume content is too short.")
    if text_len > 2500:
        score -= 5
        issues.append("Resume content is too long; keep it concise.")

    bullets = sum(1 for line in (text or "").split("\n") if line.strip().startswith(('-', '•', '*')))
    if bullets == 0:
        score -= 5
        issues.append("Use bullet points for clarity.")

    if score < 30:
        score = 30

    return score, issues


def generate_clean_resume_pdf(resume_id, resume):
    file_path = os.path.join(CLEAN_DIR, f"{resume_id}_clean_resume.pdf")

    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 60, resume.get("summary", {}).get("summary", "Professional Summary"))

    y = height - 90
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Email: {resume.get('email', 'user@example.com')}")
    y -= 24

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Summary")
    y -= 16
    c.setFont("Helvetica", 10)
    summary_text = resume.get("summary", {}).get("summary", "")
    for line in summary_text.split("\n")[:4]:
        c.drawString(50, y, line[:90])
        y -= 14

    y -= 8
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Skills")
    y -= 16
    c.setFont("Helvetica", 10)
    skills = resume.get("skills", [])
    c.drawString(50, y, ", ".join(skills[:12]))
    y -= 24

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Education")
    y -= 16
    c.setFont("Helvetica", 10)
    for edu in resume.get("summary", {}).get("education", [])[:4]:
        c.drawString(50, y, edu[:90])
        y -= 14

    y -= 6
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Experience")
    y -= 16
    c.setFont("Helvetica", 10)
    for exp in resume.get("summary", {}).get("experience", [])[:4]:
        c.drawString(50, y, exp[:90])
        y -= 14

    y -= 6
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Certifications")
    y -= 16
    c.setFont("Helvetica", 10)
    certs = resume.get("summary", {}).get("certifications", [])
    if certs:
        for cert in certs[:4]:
            c.drawString(50, y, cert[:90])
            y -= 14
    else:
        c.drawString(50, y, "None")

    c.setFont("Helvetica", 9)
    c.drawString(50, 40, "Auto-formatted by Resume Analyzer Pro")
    c.save()

    return file_path


def generate_improved_resume_pdf(resume_id, resume):
    file_path = os.path.join(CLEAN_DIR, f"{resume_id}_improved_resume.pdf")

    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 60, resume.get("summary", {}).get("summary", "Professional Summary"))

    y = height - 90
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Email: {resume.get('email', 'user@example.com')}")
    y -= 24

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Optimized Summary")
    y -= 16
    c.setFont("Helvetica", 10)
    summary_text = resume.get("summary", {}).get("summary", "Experienced professional with strong domain expertise.")
    for line in summary_text.split("\n")[:4]:
        c.drawString(50, y, line[:90])
        y -= 14

    y -= 6
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Core Skills (ATS Optimized)")
    y -= 16
    c.setFont("Helvetica", 10)
    skills = resume.get("skills", [])
    suggested = resume.get("suggested_skills", [])
    merged = skills + [s for s in suggested if s not in skills]
    c.drawString(50, y, ", ".join(merged[:14]))
    y -= 24

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Recommended Skills to Add")
    y -= 16
    c.setFont("Helvetica", 10)
    missing = resume.get("missing_skills", [])
    c.drawString(50, y, ", ".join(missing[:12]) if missing else "None")
    y -= 24

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Experience Highlights")
    y -= 16
    c.setFont("Helvetica", 10)
    highlights = resume.get("summary", {}).get("experience", [])
    if highlights and highlights != ["Fresher"]:
        for exp in highlights[:4]:
            c.drawString(50, y, f"• {exp[:85]}")
            y -= 14
    else:
        c.drawString(50, y, "• Add 2-3 impactful project or internship bullets.")
        y -= 14

    y -= 6
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Education")
    y -= 16
    c.setFont("Helvetica", 10)
    for edu in resume.get("summary", {}).get("education", [])[:4]:
        c.drawString(50, y, edu[:90])
        y -= 14

    y -= 6
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Certifications")
    y -= 16
    c.setFont("Helvetica", 10)
    certs = resume.get("summary", {}).get("certifications", [])
    if certs and certs != ["None"]:
        for cert in certs[:4]:
            c.drawString(50, y, cert[:90])
            y -= 14
    else:
        c.drawString(50, y, "• Add relevant certifications to strengthen profile.")
        y -= 14

    c.setFont("Helvetica", 9)
    c.drawString(50, 40, "Auto-optimized draft by Resume Analyzer Pro. Please review before use.")
    c.save()

    return file_path
