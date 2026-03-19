# app/main.py
from fastapi import FastAPI, UploadFile, File, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.services.parser import extract_text
from app.services.skills import extract_skills
from app.services.report import generate_pdf
from app.auth import hash_password, verify_password, create_access_token, decode_access_token
from collections import Counter
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from typing import Optional
import os, uuid
from app.services.jd_matcher import calculate_match
from app.services.suggestions import suggest_skills
from app.services.scoring import score_resume
from app.services.summary import extract_summary

app = FastAPI(title="Resume Analyzer Pro")

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

admin_user = {
    "id": 0,
    "name": "Admin",
    "email": "admin@example.com",
    "password": hash_password("Admin@123"),
    "role": "admin"
}

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://kapil_admin:kapil_admin@cluster0.veelkl6.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
client = MongoClient(MONGO_URI)

try:
    client.admin.command("ping")
    print("MongoDB Connected Successfully")
except Exception as e:
    print("MongoDB Connection Error:", e)

db = client["resume_db"]
users_collection = db["users"]
resumes_collection = db["resumes"]
jd_collection = db["job_descriptions"]
activity_collection = db["activity_logs"]

ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def format_date(dt: Optional[object]) -> str:
    if not dt:
        return "N/A"
    if isinstance(dt, str):
        return dt
    return dt.strftime("%b %d, %Y")


def log_activity(user_id: str, title: str):
    activity_collection.insert_one({
        "user_id": user_id,
        "title": title,
        "created_at": datetime.utcnow()
    })


def build_insights(skills, summary, jd_match_percent):
    section_hits = 0
    if summary.get("summary"):
        section_hits += 1
    if summary.get("education"):
        section_hits += 1
    if summary.get("experience"):
        section_hits += 1
    if summary.get("certifications"):
        section_hits += 1

    completeness = int((section_hits / 4) * 100)
    ats_readiness = min(100, int((len(skills) * 6) + (jd_match_percent * 0.6) + (completeness * 0.2)))

    tips = []
    if len(skills) < 6:
        tips.append("Add 2-3 more technical skills to improve ATS matching.")
    if jd_match_percent < 60:
        tips.append("Tailor your resume with keywords from the job description.")
    if summary.get("certifications") == ["None"]:
        tips.append("Include certifications to strengthen credibility.")
    if not tips:
        tips.append("Great work. Keep tracking score improvements over time.")

    return {
        "ats_readiness": ats_readiness,
        "completeness": completeness,
        "jd_match": jd_match_percent,
        "top_skills": skills[:6],
        "tips": tips
    }


def build_trend(resumes):
    labels = [r.get("filename") for r in resumes][::-1]
    scores = [r.get("ai_score", 0) for r in resumes][::-1]
    return {"labels": labels, "scores": scores}

def to_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")


def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    data = decode_access_token(token)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid token")
    return data

def get_optional_user(request: Request):
    token = request.cookies.get("access_token")
    return decode_access_token(token) if token else None


@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/home")


@app.get("/home", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse("home.html", {"request": request, "user": get_optional_user(request)})


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "user": get_optional_user(request)})


@app.post("/register")
def register_user(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    if users_collection.find_one({"email": email}):
        return templates.TemplateResponse("register.html", {"request": request, "error": "Email already registered"})

    hashed = hash_password(password)
    user = {"name": name, "email": email, "password": hashed, "role": "user"}
    users_collection.insert_one(user)
    return RedirectResponse("/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "user": get_optional_user(request)})


@app.post("/login")
def login_user(request: Request, email: str = Form(...), password: str = Form(...)):

    if email == admin_user["email"]:
        if verify_password(password, admin_user["password"]):
            token = create_access_token({
                "user_id": admin_user["id"],
                "role": admin_user["role"],
                "name": admin_user["name"]
            })
            response = RedirectResponse("/admin_panel", status_code=303)
            response.set_cookie("access_token", token, httponly=True, samesite="lax")
            return response
        else:
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

    user = users_collection.find_one({"email": email, "role": "user"})
    if not user or not verify_password(password, user["password"]):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

    token = create_access_token({
        "user_id": str(user["_id"]),
        "role": user["role"],
        "name": user["name"]
    })
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("access_token")
    return response


@app.get("/upload_page", response_class=HTMLResponse)
async def upload_page(request: Request, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "user":
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("upload_page.html", {"request": request, "user": current_user})


@app.post("/upload")
async def upload_resume(request: Request, file: UploadFile = File(...), jd_file: UploadFile = File(None)):
    try:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return HTMLResponse("<h2>Unsupported file type. Please upload PDF or DOCX.</h2>")

        file_id = str(uuid.uuid4())
        filepath = f"{UPLOAD_DIR}/{file_id}_{file.filename}"
        with open(filepath, "wb") as f:
            f.write(await file.read())

        text = extract_text(filepath)
        skills, skill_score = extract_skills(text)
        summary_info = extract_summary(filepath)

        jd_match_percent = 0
        missing_skills = []

        if jd_file:
            jd_ext = os.path.splitext(jd_file.filename)[1].lower()
            if jd_ext not in ALLOWED_EXTENSIONS:
                return HTMLResponse("<h2>Unsupported JD file type. Please upload PDF or DOCX.</h2>")

            jd_path = f"{UPLOAD_DIR}/{str(uuid.uuid4())}_{jd_file.filename}"
            with open(jd_path, "wb") as f:
                f.write(await jd_file.read())

            jd_text = extract_text(jd_path)
            jd_skills, _ = extract_skills(jd_text)
            match_data = calculate_match(skills, jd_skills)
            missing_skills = match_data["missing_skills"]
            jd_match_percent = int(match_data["match"]) if jd_skills else 0

        suggested_skills = suggest_skills(skills)
        ai_score = score_resume(skills, jd_match_percent, summary_info)

        token = request.cookies.get("access_token")
        current_user = decode_access_token(token)
        user_id = current_user["user_id"]

        resumes_collection.insert_one({
            "user_id": user_id,
            "filename": f"{file_id}_{file.filename}",
            "skills": skills,
            "skill_score": skill_score,
            "jd_match_percent": jd_match_percent,
            "missing_skills": missing_skills,
            "suggested_skills": suggested_skills,
            "summary": summary_info,
            "ai_score": ai_score,
            "upload_date": datetime.utcnow()
        })

        log_activity(user_id, f"Uploaded resume {file.filename}")

        return RedirectResponse(url="/dashboard", status_code=303)

    except Exception as e:
        return HTMLResponse(f"<h2>Error uploading file: {e}</h2>")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, current_user: dict = Depends(get_current_user), q: str = "", score: str = ""):

    if current_user["role"] != "user":
        return RedirectResponse("/admin_panel", status_code=303)

    filters = {"user_id": current_user["user_id"]}
    if q:
        filters["filename"] = {"$regex": q, "$options": "i"}
    if score:
        try:
            filters["ai_score"] = {"$gte": int(score)}
        except ValueError:
            pass

    user_resumes = list(resumes_collection.find(filters).sort("upload_date", -1))
    for r in user_resumes:
        r["_id"] = str(r.get("_id"))
        r["upload_date"] = format_date(r.get("upload_date"))

    if user_resumes:
        latest_resume = user_resumes[0]

        skills = latest_resume.get("skills", [])
        skill_score = latest_resume.get("skill_score", 0)
        jd_match_percent = latest_resume.get("jd_match_percent", 0)
        missing_skills = latest_resume.get("missing_skills", [])
        suggested_skills = latest_resume.get("suggested_skills", [])

        filepath = os.path.join(UPLOAD_DIR, latest_resume.get("filename"))
        summary = extract_summary(filepath)

        ai_score = latest_resume.get("ai_score", 0)
        filename = latest_resume.get("filename")

    else:
        skills = []
        skill_score = 0
        jd_match_percent = 0
        missing_skills = []
        suggested_skills = []
        summary = {}
        ai_score = 0
        filename = None

    stats = {
        "total_resumes": len(user_resumes),
        "avg_score": int(sum([r.get("ai_score", 0) for r in user_resumes]) / len(user_resumes)) if user_resumes else 0,
        "best_score": max([r.get("ai_score", 0) for r in user_resumes], default=0),
        "last_upload": format_date(user_resumes[0].get("upload_date")) if user_resumes else "N/A"
    }

    insights = build_insights(skills, summary or {}, jd_match_percent)
    stats["ats_score"] = insights.get("ats_readiness", 0)
    trend = build_trend(user_resumes[:8])
    activity_items = list(activity_collection.find({"user_id": current_user["user_id"]}).sort("created_at", -1).limit(5))
    activity = [{"title": a["title"], "time": format_date(a["created_at"])} for a in activity_items]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": current_user,
            "resumes": user_resumes,
            "skills": skills,
            "skill_score": skill_score,
            "jd_match_percent": jd_match_percent,
            "missing_skills": missing_skills,
            "suggested_skills": suggested_skills,
            "summary": summary,
            "ai_score": ai_score,
            "filename": filename,
            "stats": stats,
            "insights": insights,
            "trend": trend,
            "activity": activity,
            "query": q,
            "score_filter": score
        }
    )


@app.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "user":
        return RedirectResponse("/admin_panel", status_code=303)
    resumes = list(resumes_collection.find({"user_id": current_user["user_id"]}).sort("upload_date", -1))
    return templates.TemplateResponse("reports.html", {"request": request, "user": current_user, "resumes": resumes})

@app.get("/help", response_class=HTMLResponse)
def help_center(request: Request):
    return templates.TemplateResponse("help_center.html", {"request": request, "user": get_optional_user(request)})

@app.get("/privacy", response_class=HTMLResponse)
def privacy_policy(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request, "user": get_optional_user(request)})

@app.get("/terms", response_class=HTMLResponse)
def terms_conditions(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request, "user": get_optional_user(request)})

@app.get("/faq", response_class=HTMLResponse)
def faq_page(request: Request):
    return templates.TemplateResponse("faq.html", {"request": request, "user": get_optional_user(request)})

@app.get("/contact", response_class=HTMLResponse)
def contact_page(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request, "user": get_optional_user(request)})


@app.get("/download/{filename}")
def download_report(request: Request, filename: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] == "admin":
        resume = resumes_collection.find_one({"filename": filename})
    else:
        resume = resumes_collection.find_one({"user_id": current_user["user_id"], "filename": filename})
    if not resume:
        raise HTTPException(status_code=404, detail="Report not found")
    report_path = f"reports/{filename}_report.pdf"
    if not os.path.exists(report_path):
        report_path = generate_pdf(filename, resume)
    return FileResponse(report_path, media_type="application/pdf", filename=os.path.basename(report_path))


@app.delete("/resumes/delete/{resume_id}")
def delete_resume(resume_id: str, current_user: dict = Depends(get_current_user)):
    resume = resumes_collection.find_one({"_id": to_object_id(resume_id), "user_id": current_user["user_id"]})
    if not resume:
        return JSONResponse({"status": "error"}, status_code=404)
    resumes_collection.delete_one({"_id": to_object_id(resume_id)})
    file_path = os.path.join(UPLOAD_DIR, resume["filename"])
    if os.path.exists(file_path):
        os.remove(file_path)
    log_activity(current_user["user_id"], f"Deleted resume {resume['filename']}")
    return JSONResponse({"status": "success"})


@app.put("/resumes/update/{resume_id}")
async def update_resume(resume_id: str, file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    resume = resumes_collection.find_one({"_id": to_object_id(resume_id), "user_id": current_user["user_id"]})
    if not resume:
        return JSONResponse({"status": "error"}, status_code=404)
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return JSONResponse({"status": "error"}, status_code=400)
    filepath = os.path.join(UPLOAD_DIR, resume["filename"])
    with open(filepath, "wb") as f:
        f.write(await file.read())
    text = extract_text(filepath)
    skills, skill_score = extract_skills(text)
    summary_info = extract_summary(filepath)
    ai_score = score_resume(skills, resume.get("jd_match_percent", 0), summary_info)
    resumes_collection.update_one(
        {"_id": to_object_id(resume_id)},
        {"$set": {"skills": skills, "skill_score": skill_score, "summary": summary_info, "ai_score": ai_score}}
    )
    log_activity(current_user["user_id"], f"Updated resume {resume['filename']}")
    return JSONResponse({"status": "updated"})


@app.get("/resume/{resume_id}", response_class=HTMLResponse)
def resume_detail(request: Request, resume_id: str, current_user: dict = Depends(get_current_user)):
    resume = resumes_collection.find_one({"_id": to_object_id(resume_id), "user_id": current_user["user_id"]})
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    resume.setdefault("summary", {"summary": "", "education": [], "experience": [], "certifications": []})
    resume.setdefault("skills", [])
    resume.setdefault("missing_skills", [])
    resume.setdefault("suggested_skills", [])
    resume["upload_date"] = format_date(resume.get("upload_date"))
    insights = build_insights(resume.get("skills", []), resume.get("summary", {}), resume.get("jd_match_percent", 0))
    return templates.TemplateResponse("resume_detail.html", {"request": request, "user": current_user, "resume": resume, "insights": insights})


@app.get("/compare", response_class=HTMLResponse)
def compare_resumes(request: Request, current_user: dict = Depends(get_current_user), left: str = "", right: str = ""):
    resumes = list(resumes_collection.find({"user_id": current_user["user_id"]}).sort("upload_date", -1))
    for r in resumes:
        r["_id"] = str(r.get("_id"))
    comparison = None
    if left and right:
        left_doc = resumes_collection.find_one({"_id": to_object_id(left), "user_id": current_user["user_id"]})
        right_doc = resumes_collection.find_one({"_id": to_object_id(right), "user_id": current_user["user_id"]})
        if left_doc and right_doc:
            left_skills = set([s.lower() for s in left_doc.get("skills", [])])
            right_skills = set([s.lower() for s in right_doc.get("skills", [])])
            comparison = {
                "left": left_doc,
                "right": right_doc,
                "only_left": sorted(list(left_skills - right_skills)),
                "only_right": sorted(list(right_skills - left_skills)),
                "common": sorted(list(left_skills & right_skills))
            }
    return templates.TemplateResponse(
        "compare.html",
        {
            "request": request,
            "user": current_user,
            "resumes": resumes,
            "comparison": comparison,
            "selected_left": left,
            "selected_right": right
        }
    )


@app.get("/jd-library", response_class=HTMLResponse)
def jd_library(request: Request, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "user":
        return RedirectResponse("/admin_panel", status_code=303)
    jd_items = list(jd_collection.find({"user_id": current_user["user_id"]}).sort("created_at", -1))
    for jd in jd_items:
        jd["_id"] = str(jd.get("_id"))
        jd["created_at"] = format_date(jd.get("created_at"))
    return templates.TemplateResponse("jd_library.html", {"request": request, "user": current_user, "jd_items": jd_items})


@app.post("/jd-library")
async def add_jd(request: Request, current_user: dict = Depends(get_current_user), title: str = Form(...), jd_text: str = Form(""), jd_file: UploadFile = File(None)):
    if current_user["role"] != "user":
        return RedirectResponse("/admin_panel", status_code=303)
    content = jd_text
    if jd_file:
        jd_ext = os.path.splitext(jd_file.filename)[1].lower()
        if jd_ext not in ALLOWED_EXTENSIONS:
            return HTMLResponse("<h2>Unsupported JD file type. Please upload PDF or DOCX.</h2>")
        jd_path = f"{UPLOAD_DIR}/{str(uuid.uuid4())}_{jd_file.filename}"
        with open(jd_path, "wb") as f:
            f.write(await jd_file.read())
        content = extract_text(jd_path)
    jd_collection.insert_one({
        "user_id": current_user["user_id"],
        "title": title,
        "content": content,
        "created_at": datetime.utcnow()
    })
    log_activity(current_user["user_id"], f"Saved JD: {title}")
    return RedirectResponse("/jd-library", status_code=303)


@app.delete("/jd-library/{jd_id}")
def delete_jd(jd_id: str, current_user: dict = Depends(get_current_user)):
    jd_collection.delete_one({"_id": to_object_id(jd_id), "user_id": current_user["user_id"]})
    return JSONResponse({"status": "success"})


@app.get("/admin_panel", response_class=HTMLResponse)
def admin_panel(request: Request, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        return RedirectResponse("/dashboard", status_code=303)
    users = list(users_collection.find({}))
    resumes = list(resumes_collection.find({}))
    user_name_map = {str(u.get("_id")): u.get("name") for u in users}
    for r in resumes:
        r["_id"] = str(r.get("_id"))
        r["upload_date"] = format_date(r.get("upload_date"))
        r["user_name"] = user_name_map.get(r.get("user_id"), r.get("user_id"))
    total_users = len(users)
    total_resumes = len(resumes)
    user_ids_with_resumes = set([r.get("user_id") for r in resumes])
    active_users = len([u for u in users if str(u.get("_id")) in user_ids_with_resumes])
    inactive_users = max(total_users - active_users, 0)

    skill_counter = Counter()
    scores = []
    for r in resumes:
        for s in r.get("skills", []):
            skill_counter[s] += 1
        scores.append(r.get("ai_score", 0))
    top_skills = skill_counter.most_common(10)
    avg_score = int(sum(scores) / len(scores)) if scores else 0

    return templates.TemplateResponse(
        "admin_panel.html",
        {
            "request": request,
            "user": current_user,
            "users": [{"id": str(u.get("_id")), "name": u.get("name"), "email": u.get("email"), "role": u.get("role", "user")} for u in users],
            "resumes": resumes,
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "total_resumes": total_resumes,
            "total_analyzed": total_resumes,
            "top_skills": top_skills,
            "avg_score": avg_score,
            "today_uploads": len([r for r in resumes if r.get("upload_date") == format_date(datetime.utcnow())])
        }
    )

@app.get("/admin/users", response_class=HTMLResponse)
def admin_users(request: Request, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        return RedirectResponse("/dashboard", status_code=303)
    users = list(users_collection.find({}))
    resumes = list(resumes_collection.find({}))
    resume_count = {}
    for r in resumes:
        resume_count[r.get("user_id")] = resume_count.get(r.get("user_id"), 0) + 1
    user_rows = []
    for u in users:
        uid = str(u.get("_id"))
        user_rows.append({
            "id": uid,
            "name": u.get("name"),
            "email": u.get("email"),
            "role": u.get("role", "user"),
            "total_resumes": resume_count.get(uid, 0)
        })
    return templates.TemplateResponse("admin_users.html", {"request": request, "user": current_user, "users": user_rows})

@app.get("/admin/resumes", response_class=HTMLResponse)
def admin_resumes(request: Request, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        return RedirectResponse("/dashboard", status_code=303)
    resumes = list(resumes_collection.find({}).sort("upload_date", -1))
    for r in resumes:
        r["_id"] = str(r.get("_id"))
        r["upload_date"] = format_date(r.get("upload_date"))
    return templates.TemplateResponse("admin_resumes.html", {"request": request, "user": current_user, "resumes": resumes})

@app.post("/admin/resumes/delete/{resume_id}")
def admin_delete_resume(resume_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        return RedirectResponse("/dashboard", status_code=303)
    resume = resumes_collection.find_one({"_id": to_object_id(resume_id)})
    if resume:
        resumes_collection.delete_one({"_id": to_object_id(resume_id)})
        file_path = os.path.join(UPLOAD_DIR, resume["filename"])
        if os.path.exists(file_path):
            os.remove(file_path)
    return RedirectResponse("/admin/resumes", status_code=303)

@app.get("/admin/resume/{resume_id}", response_class=HTMLResponse)
def admin_resume_detail(request: Request, resume_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        return RedirectResponse("/dashboard", status_code=303)
    resume = resumes_collection.find_one({"_id": to_object_id(resume_id)})
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    resume.setdefault("summary", {"summary": "", "education": [], "experience": [], "certifications": []})
    resume.setdefault("skills", [])
    resume.setdefault("missing_skills", [])
    resume.setdefault("suggested_skills", [])
    resume["_id"] = str(resume.get("_id"))
    resume["upload_date"] = format_date(resume.get("upload_date"))
    insights = build_insights(resume.get("skills", []), resume.get("summary", {}), resume.get("jd_match_percent", 0))
    return templates.TemplateResponse("admin_resume_detail.html", {"request": request, "user": current_user, "resume": resume, "insights": insights})

@app.get("/admin/reports", response_class=HTMLResponse)
def admin_reports(request: Request, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        return RedirectResponse("/dashboard", status_code=303)
    resumes = list(resumes_collection.find({}).sort("upload_date", -1))
    for r in resumes:
        r["_id"] = str(r.get("_id"))
        r["upload_date"] = format_date(r.get("upload_date"))
    return templates.TemplateResponse("admin_reports.html", {"request": request, "user": current_user, "resumes": resumes})

@app.get("/admin/settings", response_class=HTMLResponse)
def admin_settings(request: Request, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("admin_settings.html", {"request": request, "user": current_user})
