def suggest_skills(missing_skills):

    suggestions = []

    for skill in missing_skills:
        suggestions.append(skill.title())

    return suggestions