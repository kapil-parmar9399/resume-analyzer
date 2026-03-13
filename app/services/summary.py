import re
import docx2txt
import pdfplumber

def extract_text(filepath):
    """Extract text from PDF or DOCX."""
    text = ""
    if filepath.endswith(".pdf"):
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    elif filepath.endswith(".docx"):
        text = docx2txt.process(filepath)
    return text

def extract_summary(filepath):
    """Extract compact Profile, Education, Experience, Certifications."""
    text = extract_text(filepath)
    text = re.sub(r'\s+', ' ', text)  # remove excessive whitespace
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    summary_info = {}

    # 🔹 Profile: first proper name (all caps or Capitalized)
    name_match = re.search(r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b", text)
    summary_info["summary"] = name_match.group(1) if name_match else "Profile summary not available"

    # 🔹 Education: only 10th, 12th, degree name
    education = []
    # Match 10th, 12th
    edu_10 = re.search(r"10th.*?Board|10th.*?\d{4}", text, re.IGNORECASE)
    edu_12 = re.search(r"12th.*?School|12th.*?\d{4}", text, re.IGNORECASE)
    # Match Degree
    degree = re.search(r"(Bachelor.*?|B\.Tech|B\.E|Master.*?|M\.Tech|MCA|BSc|MSc)", text, re.IGNORECASE)

    if edu_10:
        education.append(edu_10.group(0).strip())
    if edu_12:
        education.append(edu_12.group(0).strip())
    if degree:
        education.append(degree.group(0).strip())

    summary_info["education"] = education if education else ["Education info not extracted"]

    # 🔹 Experience: Fresher or years of experience only
    exp_match = re.search(r'(\d+\s*years.*?experience|Fresher|fresher)', text, re.IGNORECASE)
    summary_info["experience"] = [exp_match.group(0).strip()] if exp_match else ["Fresher"]

    # 🔹 Certifications: only certificate names
    cert_keywords = ['Certified', 'Certification', 'AWS', 'Google', 'Microsoft', 'Oracle', 'NPTEL', 'Python', 'C\+\+', 'C#', 'CCNA', 'Scrum', 'ITIL']
    certs = []
    for kw in cert_keywords:
        matches = re.findall(rf"{kw}[\w\s\-&,]*", text, re.IGNORECASE)
        for m in matches:
            cert_name = m.strip().replace('--', '').replace('-', '').strip()
            if cert_name not in certs:
                certs.append(cert_name)
    summary_info["certifications"] = certs if certs else ["No certifications"]

    return summary_info