# app/main.py
from fastapi import FastAPI, UploadFile, File, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
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
import os, uuid
from app.services.jd_matcher import calculate_match
from app.services.suggestions import suggest_skills
# from app.services.summary import extract_summary
# from app.services.scorer import score_resume
from app.services.scoring import score_resume

app = FastAPI(title="Professional Resume Analyzer")

# Templates & Static
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Upload folder
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -----------------------------
# Predefined Admin
# -----------------------------
admin_user = {
    "id": 0,
    "name": "Admin",
    "email": "admin@example.com",
    "password": hash_password("Admin@123"),
    "role": "admin"
}

# -----------------------------
# MongoDB Setup
# -----------------------------
MONGO_URI = "mongodb+srv://kapil_admin:kapil_admin@cluster0.veelkl6.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

client = MongoClient(MONGO_URI)

try:
    client.admin.command('ping')
    print("✅ MongoDB Connected Successfully")
except Exception as e:
    print("❌ MongoDB Connection Error:", e)

db = client["resume_db"]
users_collection = db["users"]
resumes_collection = db["resumes"]

# -----------------------------
# Current user dependency
# -----------------------------
def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    data = decode_access_token(token)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid token")
    return data

# -----------------------------
# Landing / Home page
# -----------------------------
@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/home")

@app.get("/home", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

# -----------------------------
# Register / Login
# -----------------------------
@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register_user(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    if users_collection.find_one({"email": email}):
        return templates.TemplateResponse("register.html", {"request": request, "error": "Email already registered"})
    
    hashed = hash_password(password)
    user = {
        "name": name,
        "email": email,
        "password": hashed,
        "role": "user"
    }
    users_collection.insert_one(user)
    return RedirectResponse("/login", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

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
            response.set_cookie("access_token", token)
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
    response.set_cookie("access_token", token)
    return response

# -----------------------------
# Logout
# -----------------------------
@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("access_token")
    return response

# -----------------------------
# Upload Resume page
# -----------------------------
@app.get("/upload_page", response_class=HTMLResponse)
async def upload_page(request: Request, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "user":
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("upload_page.html", {"request": request, "user": current_user})

# -----------------------------
# Upload Resume & Analysis
# -----------------------------
from app.services.summary import extract_summary  # <- import kiya upar
# rest of your imports same as before

@app.post("/upload")
async def upload_resume(request: Request, file: UploadFile = File(...), jd_file: UploadFile = File(None)):
    try:
        import uuid
        from datetime import datetime

        # 1️⃣ Save uploaded resume
        file_id = str(uuid.uuid4())
        filepath = f"{UPLOAD_DIR}/{file_id}_{file.filename}"
        with open(filepath, "wb") as f:
            f.write(await file.read())

        # 2️⃣ Extract resume text
        text = extract_text(filepath)

        # 3️⃣ Extract skills
        skills, skill_score = extract_skills(text)

        # 4️⃣ Extract Profile, Education, Experience, Certifications using robust parser
        summary_info = extract_summary(filepath)  # ✅ updated here, replaces all regex

        # 5️⃣ Handle optional Job Description (JD) file
        jd_match_percent = 0
        missing_skills = []
        if jd_file:
            jd_path = f"{UPLOAD_DIR}/{str(uuid.uuid4())}_{jd_file.filename}"
            with open(jd_path, "wb") as f:
                f.write(await jd_file.read())
            jd_text = extract_text(jd_path)
            jd_skills, _ = extract_skills(jd_text)

            matched_skills = [s for s in skills if s in jd_skills]
            missing_skills = [s for s in jd_skills if s not in skills]
            jd_match_percent = int(len(matched_skills)/len(jd_skills)*100) if jd_skills else 0

        # 6️⃣ Suggest industry skills (optional)
        suggested_skills = suggest_skills(skills)

        # 7️⃣ Calculate AI-based resume score
        ai_score = score_resume(skills, jd_match_percent, summary_info)

        # 8️⃣ Get current user info
        token = request.cookies.get("access_token")
        current_user = decode_access_token(token)
        user_id = current_user["user_id"]

        # 9️⃣ Save resume info to MongoDB
        resumes_collection.insert_one({
            "user_id": user_id,
            "filename": f"{file_id}_{file.filename}",
            "skills": skills,
            "skill_score": skill_score,
            "jd_match_percent": jd_match_percent,
            "missing_skills": missing_skills,
            "suggested_skills": suggested_skills,
            "summary": summary_info,  # ✅ now robust
            "ai_score": ai_score,
            "upload_date": datetime.utcnow()
        })

        # 🔟 Fetch all resumes of user
        user_resumes = list(resumes_collection.find({"user_id": user_id}))

        # 1️⃣1️⃣ Render dashboard
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
                "summary": summary_info,  # ✅ dashboard me ab properly dikhega
                "ai_score": ai_score,
                "filename": f"{file_id}_{file.filename}"
            }
        )

    except Exception as e:
        return HTMLResponse(f"<h2>Error uploading file: {e}</h2>")
# Dashboard
# -----------------------------
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, current_user: dict = Depends(get_current_user)):

    if current_user["role"] != "user":
        return RedirectResponse("/admin_panel", status_code=303)

    user_resumes = list(resumes_collection.find({"user_id": current_user["user_id"]}))

    if user_resumes:
        latest_resume = user_resumes[-1]
        skills = latest_resume.get("skills", [])
        score = latest_resume.get("score", 0)
        filename = latest_resume.get("filename")
    else:
        skills = []
        score = 0
        filename = None

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": current_user,
            "resumes": user_resumes,
            "skills": skills,
            "score": score,
            "filename": filename
        }
    )

# -----------------------------
# Download PDF report
# -----------------------------
@app.get("/download/{filename}")
async def download_report(filename: str):
    try:
        report_file = generate_pdf(filename)
        return FileResponse(report_file, media_type="application/pdf", filename=f"{filename}_report.pdf")
    except Exception as e:
        return HTMLResponse(f"<h2>Error generating report: {e}</h2>")

# -----------------------------
# Admin Panel
# -----------------------------
@app.get("/admin_panel", response_class=HTMLResponse)
async def admin_panel(request: Request, current_user: dict = Depends(get_current_user)):

    if current_user["role"] != "admin":
        return RedirectResponse("/dashboard", status_code=303)

    users_list = list(users_collection.find())
    resumes_list = list(resumes_collection.find())

    # Convert MongoDB _id to string for template
    for u in users_list:
        u["id"] = str(u["_id"])
    for r in resumes_list:
        r["id"] = str(r["_id"])

    total_users = len(users_list)
    active_users = sum(
        1 for u in users_list if any(r["user_id"] == str(u["_id"]) for r in resumes_list)
    )
    inactive_users = total_users - active_users
    total_resumes = len(resumes_list)
    total_analyzed = sum(1 for r in resumes_list if r.get("skills"))
    all_skills = []
    for r in resumes_list:
        all_skills.extend(r.get("skills", []))
    top_skills = Counter(all_skills).most_common(10)

    last_upload = None
    if resumes_list:
        last_resume = sorted(resumes_list, key=lambda x: x["_id"], reverse=True)[0]
        last_upload = last_resume.get("upload_date")

    return templates.TemplateResponse(
        "admin_panel.html",
        {
            "request": request,
            "users": users_list,
            "resumes": resumes_list,
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "total_resumes": total_resumes,
            "total_analyzed": total_analyzed,
            "top_skills": top_skills,
            "last_upload": last_upload,
            "admin_name": current_user["name"]
        }
    )

# -----------------------------
# Reports page
# -----------------------------
@app.get("/reports", response_class=HTMLResponse)
async def user_reports(request: Request, current_user: dict = Depends(get_current_user)):

    if current_user["role"] != "user":
        return RedirectResponse("/dashboard", status_code=303)

    user_resumes = list(resumes_collection.find({"user_id": current_user["user_id"]}))

    return templates.TemplateResponse(
        "reports.html",
        {
            "request": request,
            "resumes": user_resumes,
            "user": current_user
        }
    )

# -----------------------------
# -----------------------------
# Added: Resume Delete & Update routes
# -----------------------------
@app.delete("/resumes/delete/{resume_id}")
async def delete_resume(resume_id: str, current_user: dict = Depends(get_current_user)):
    resume = resumes_collection.find_one({"_id": ObjectId(resume_id)})
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if resume["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Delete from DB
    resumes_collection.delete_one({"_id": ObjectId(resume_id)})
    
    # Delete file from uploads folder
    filepath = os.path.join(UPLOAD_DIR, resume["filename"])
    if os.path.exists(filepath):
        os.remove(filepath)
    
    return {"status": "success"}

@app.put("/resumes/update/{resume_id}")
async def update_resume(resume_id: str, file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    resume = resumes_collection.find_one({"_id": ObjectId(resume_id)})
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if resume["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Save new file
    file_id = str(uuid.uuid4())
    filepath = f"{UPLOAD_DIR}/{file_id}_{file.filename}"
    with open(filepath, "wb") as f:
        f.write(await file.read())

    # Re-extract skills & score
    text = extract_text(filepath)
    skills, score = extract_skills(text)

    # Update DB
    resumes_collection.update_one(
        {"_id": ObjectId(resume_id)},
        {"$set": {"filename": f"{file_id}_{file.filename}", "skills": skills, "score": score, "upload_date": datetime.utcnow()}}
    )
    
    return {"status": "updated", "filename": f"{file_id}_{file.filename}", "score": score, "skills": skills}