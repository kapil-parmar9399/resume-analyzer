import re
import docx2txt
import pdfplumber


def extract_text(filepath):
    """Extract text from PDF or DOCX resume."""
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
    """Extract profile summary, education, experience, certifications."""
    text = extract_text(filepath)

    summary_info = {
        "summary": "",
        "education": [],
        "experience": [],
        "certifications": []
    }

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # -------------------
    # Profile Summary
    # -------------------
    summary_lines = []
    for line in lines[:10]:
        if len(line) > 30:
            summary_lines.append(line)

    summary_info["summary"] = "\n".join(summary_lines[:4]) if summary_lines else "No summary available"

    # -------------------
    # Education
    # -------------------
    edu_keywords = ["B.Tech", "Bachelor", "M.Tech", "Master", "Diploma", "B.E"]

    summary_info["education"] = [
        line for line in lines
        if any(k.lower() in line.lower() for k in edu_keywords)
    ]

    if not summary_info["education"]:
        summary_info["education"] = ["Education info not extracted"]

    # -------------------
    # Experience
    # -------------------
    exp_keywords = ["experience", "intern", "worked", "company"]

    summary_info["experience"] = [
        line for line in lines
        if any(k in line.lower() for k in exp_keywords)
    ]

    if not summary_info["experience"]:
        summary_info["experience"] = ["Fresher"]

    # -------------------
    # Certifications (ULTIMATE FINAL FIX)
    # -------------------
    cert_list = []
    seen = set()

    cert_start = -1

    # Step 1: Find Certifications heading
    for i, line in enumerate(lines):
        if "certification" in line.lower():
            cert_start = i
            break

    # Step 2: If no section found → None
    if cert_start == -1:
        summary_info["certifications"] = ["None"]
        return summary_info

    # Step 3: Take only next few lines (safe range)
    cert_lines = lines[cert_start + 1: cert_start + 7]

    for line in cert_lines:

        # Stop if next section starts
        if any(word in line.lower() for word in ["skills", "projects", "experience", "education"]):
            break

        items = line.split(",")

        for item in items:
            item = item.strip()

            if not item:
                continue

            # ❌ Reject long sentences
            if len(item.split()) > 5:
                continue

            # ❌ Reject descriptive words
            if any(word in item.lower() for word in ["and", "using", "build", "generate", "system", "analysis"]):
                continue

            # ✅ Accept only clean text (letters, numbers, +, #)
            if re.match(r"^[a-zA-Z0-9\+\# ]+$", item):
                cert_name = item.title()

                if cert_name and cert_name not in seen:
                    seen.add(cert_name)
                    cert_list.append(cert_name)

    # Step 4: Final fallback
    if not cert_list:
        cert_list = ["None"]

    summary_info["certifications"] = cert_list

    return summary_info