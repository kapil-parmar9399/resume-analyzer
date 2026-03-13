def calculate_match(resume_skills, jd_skills):

    resume_skills = set([s.lower() for s in resume_skills])
    jd_skills = set([s.lower() for s in jd_skills])

    matched = resume_skills.intersection(jd_skills)

    match_percentage = 0
    if len(jd_skills) > 0:
        match_percentage = (len(matched) / len(jd_skills)) * 100

    missing = jd_skills - resume_skills

    return {
        "match": round(match_percentage,2),
        "matched_skills": list(matched),
        "missing_skills": list(missing)
    }