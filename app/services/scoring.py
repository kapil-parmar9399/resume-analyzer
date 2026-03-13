def score_resume(skills, match_percentage, summary):
    """
    Calculate AI-based resume score based on:
    - Number of skills
    - JD match percentage
    - Presence of experience, education, certifications
    Returns a score out of 100.
    """
    score = 0

    # Skills count
    if len(skills) >= 8:
        score += 25
    elif len(skills) >= 5:
        score += 20
    else:
        score += 10

    # JD match
    if match_percentage >= 80:
        score += 25
    elif match_percentage >= 60:
        score += 20
    elif match_percentage >= 40:
        score += 15
    else:
        score += 5

    # Experience
    if summary.get("experience") and len(summary["experience"]) > 0:
        score += 25
    else:
        score += 5

    # Education
    if summary.get("education") and len(summary["education"]) > 0:
        score += 15
    else:
        score += 5

    # Certifications
    if summary.get("certifications") and len(summary["certifications"]) > 0:
        score += 10
    else:
        score += 0

    # Ensure score does not exceed 100
    final_score = min(score, 100)
    return final_score