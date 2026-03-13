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
    else:
        text = ""
    return text


def extract_summary(filepath):
    """Extract profile summary, education, experience, certifications."""
    text = extract_text(filepath)
    summary_info = {}

    # 1️⃣ Profile / Summary
    profile_match = re.search(
        r"(Profile|Summary|Professional Summary|Career Summary):(.*?)(Education|Experience|Certifications|$)",
        text, re.DOTALL | re.IGNORECASE)
    profile_summary = profile_match.group(2).strip() if profile_match else ""

    # fallback: first 5 meaningful lines (>20 chars)
    if not profile_summary:
        lines = text.split('\n')
        meaningful = [line.strip() for line in lines if len(line.strip()) > 20]
        profile_summary = "\n".join(meaningful[:5]) if meaningful else "Profile summary not available"

    summary_info["summary"] = profile_summary

    # 2️⃣ Education
    edu_match = re.search(
        r"(Education|Academic Background|Qualifications):(.*?)(Experience|Certifications|$)",
        text, re.DOTALL | re.IGNORECASE)
    education_text = edu_match.group(2).strip() if edu_match else ""
    if education_text:
        summary_info["education"] = [line.strip() for line in education_text.split("\n") if line.strip()]
    else:
        # fallback: keywords
        edu_keywords = ['Bachelor', 'B.Tech', 'Master', 'M.Tech', 'Diploma', 'Certification']
        summary_info["education"] = [line.strip() for line in text.split('\n') if any(word in line for word in edu_keywords)]
        if not summary_info["education"]:
            summary_info["education"] = ["Education info not extracted"]

    # 3️⃣ Experience
    exp_match = re.search(
        r"(Experience|Work Experience|Employment History):(.*?)(Certifications|$)",
        text, re.DOTALL | re.IGNORECASE)
    experience_text = exp_match.group(2).strip() if exp_match else ""
    if experience_text:
        summary_info["experience"] = [line.strip() for line in experience_text.split("\n") if line.strip()]
    else:
        # fallback: keywords
        exp_keywords = ['Experience', 'Worked', 'Internship', 'Projects', 'Responsibilities']
        summary_info["experience"] = [line.strip() for line in text.split('\n') if any(word in line for word in exp_keywords)]
        if not summary_info["experience"]:
            summary_info["experience"] = ["Experience info not extracted"]

    # 4️⃣ Certifications
    cert_match = re.search(
        r"(Certifications|Certs|Licenses):(.*)$",
        text, re.DOTALL | re.IGNORECASE)
    certifications_text = cert_match.group(2).strip() if cert_match else ""
    if certifications_text:
        summary_info["certifications"] = [line.strip() for line in certifications_text.split("\n") if line.strip()]
    else:
        # fallback: keywords
        cert_keywords = ['Certified', 'Certification', 'AWS', 'Google', 'Microsoft', 'Oracle']
        summary_info["certifications"] = [line.strip() for line in text.split('\n') if any(word in line for word in cert_keywords)]
        if not summary_info["certifications"]:
            summary_info["certifications"] = ["Certifications info not extracted"]

    return summary_info