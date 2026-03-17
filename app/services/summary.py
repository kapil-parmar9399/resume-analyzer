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

    # ⚠️ IMPORTANT: newline preserve karo (pehle wali mistake fix)
    text = re.sub(r'[ \t]+', ' ', text)

    lines = [line.strip() for line in text.split('\n') if line.strip()]

    summary_info = {}

    # 🔹 Profile (Name)
    name_match = re.search(r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b", text)
    summary_info["summary"] = name_match.group(1) if name_match else "Profile summary not available"

    # 🔹 Education
    education = []

    edu_10 = re.search(r"10th.*?(\d{4})", text, re.IGNORECASE)
    edu_12 = re.search(r"12th.*?(\d{4})", text, re.IGNORECASE)
    degree = re.search(r"(B\.Tech|B\.E|Bachelor.*?|M\.Tech|MCA|BSc|MSc|Master.*?)", text, re.IGNORECASE)

    if edu_10:
        education.append(edu_10.group(0).strip())
    if edu_12:
        education.append(edu_12.group(0).strip())
    if degree:
        education.append(degree.group(0).strip())

    summary_info["education"] = education if education else ["Education info not extracted"]

    # 🔹 Experience
    exp_match = re.search(r'(\d+\s*years.*?experience|Fresher|fresher)', text, re.IGNORECASE)
    summary_info["experience"] = [exp_match.group(0).strip()] if exp_match else ["Fresher"]

    # 🔹 Certifications (🔥 FINAL CLEAN FIX)
    certs = []
    seen = set()

    cert_start = -1

    # Step 1: Find Certifications section line
    for i, line in enumerate(lines):
        if "certification" in line.lower():
            cert_start = i
            break

    if cert_start != -1:
        # Step 2: Take only next few lines (safe range)
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

                # ✅ Accept only clean names
                if re.match(r"^[a-zA-Z0-9\+\# ]+$", item):
                    cert_name = item.title()

                    if cert_name not in seen:
                        seen.add(cert_name)
                        certs.append(cert_name)

    # Step 3: Final fallback
    summary_info["certifications"] = certs if certs else ["None"]

    return summary_info