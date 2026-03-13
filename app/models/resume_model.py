from app.database import resumes_collection

def save_resume(data):

    resumes_collection.insert_one(data)