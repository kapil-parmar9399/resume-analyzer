from rapidfuzz import process

# Predefined skill set for matching
JOB_SKILLS = [
    "Python", "Java", "C++", "SQL", "Django", "FastAPI",
    "Machine Learning", "AI", "Data Analysis", "React",
    "HTML", "CSS", "JavaScript"
]

def extract_skills(text):
    """
    Extract skills from resume text.
    Returns:
        matched_skills: List of detected skills
        skill_score: % of skills matched from JOB_SKILLS
    """
    text_lower = text.lower()
    matched = []
    for skill in JOB_SKILLS:
        if skill.lower() in text_lower:
            matched.append(skill)
    score = int(len(matched) / len(JOB_SKILLS) * 100) if JOB_SKILLS else 0
    return matched, score

def jd_skill_match(resume_skills, jd_skills):
    """
    Match resume skills against Job Description (JD) skills.
    Returns:
        match_percent: % of JD skills found in resume
        missing_skills: list of skills missing in resume
    """
    resume_set = set([s.lower() for s in resume_skills])
    jd_set = set([s.lower() for s in jd_skills])
    
    matched = resume_set.intersection(jd_set)
    missing = jd_set - resume_set
    
    match_percent = round(len(matched) / len(jd_set) * 100, 2) if jd_set else 0
    
    return match_percent, list(missing)

def suggest_skills(resume_skills, industry_keywords=None):
    """
    Suggest missing skills based on industry keywords.
    Returns:
        missing_skills: list of suggested skills not in resume
    """
    if industry_keywords is None:
        industry_keywords = ["Python","Django","FastAPI","SQL","Machine Learning","AI","Data Analysis","React","HTML","CSS","JavaScript"]
    
    resume_set = set([s.lower() for s in resume_skills])
    missing_skills = [skill for skill in industry_keywords if skill.lower() not in resume_set]
    
    return missing_skills