# app/models.py
from pydantic import BaseModel
from typing import Optional
from bson import ObjectId
from app.database import db  # MongoDB connection

class User(BaseModel):
    id: str
    username: str
    email: str
    hashed_password: str

    @classmethod
    def get_by_username(cls, username: str):
        user_data = db["users"].find_one({"username": username})
        if user_data:
            return User(
                id=str(user_data["_id"]),
                username=user_data["username"],
                email=user_data["email"],
                hashed_password=user_data["hashed_password"]
            )
        return None

    @classmethod
    def get_by_id(cls, user_id: str):
        user_data = db["users"].find_one({"_id": ObjectId(user_id)})
        if user_data:
            return User(
                id=str(user_data["_id"]),
                username=user_data["username"],
                email=user_data["email"],
                hashed_password=user_data["hashed_password"]
            )
        return None