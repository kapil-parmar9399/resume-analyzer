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
from app.services.scoring import score_resume
from app.services.summary import extract_summary  # already present

app = FastAPI(title="Professional Resume Analyzer")

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

def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    data = decode_access_token(token)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid token")
    return data

@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/home")

@app.get("/home", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

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
            jd_path = f"{UPLOAD_DIR}/{str(uuid.uuid4())}_{jd_file.filename}"
            with open(jd_path, "wb") as f:
                f.write(await jd_file.read())

            jd_text = extract_text(jd_path)
            jd_skills, _ = extract_skills(jd_text)

            matched_skills = [s for s in skills if s in jd_skills]
            missing_skills = [s for s in jd_skills if s not in skills]

            jd_match_percent = int(len(matched_skills) / len(jd_skills) * 100) if jd_skills else 0

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

        return RedirectResponse(url="/dashboard", status_code=303)

    except Exception as e:
        return HTMLResponse(f"<h2>Error uploading file: {e}</h2>")


# -----------------------------
# Dashboard (ONLY FIX HERE)
# -----------------------------
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, current_user: dict = Depends(get_current_user)):

    if current_user["role"] != "user":
        return RedirectResponse("/admin_panel", status_code=303)

    user_resumes = list(
        resumes_collection.find({"user_id": current_user["user_id"]}).sort("upload_date", -1)
    )

    if user_resumes:
        latest_resume = user_resumes[0]

        skills = latest_resume.get("skills", [])
        skill_score = latest_resume.get("skill_score", 0)
        jd_match_percent = latest_resume.get("jd_match_percent", 0)
        missing_skills = latest_resume.get("missing_skills", [])
        suggested_skills = latest_resume.get("suggested_skills", [])

        # 🔥 FIX: fresh parsing instead of DB summary
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
            "filename": filename
        }
    )