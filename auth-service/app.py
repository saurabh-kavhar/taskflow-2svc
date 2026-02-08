import os
from datetime import datetime, timedelta

from flask import Flask, request, jsonify
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

import jwt
from passlib.context import CryptContext

DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET", "supersecret")
JWT_ALG = "HS256"
JWT_EXP_HOURS = 24

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def create_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXP_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_token(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None

app = Flask(__name__)

@app.before_first_request
def startup():
    init_db()

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/auth/register")
def register():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email and password required"}), 400

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return jsonify({"error": "email already registered"}), 409

        user = User(email=email, password_hash=pwd_context.hash(password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return jsonify({"id": user.id, "email": user.email})
    finally:
        db.close()

@app.post("/auth/login")
def login():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user or not pwd_context.verify(password, user.password_hash):
            return jsonify({"error": "invalid credentials"}), 401

        token = create_token(user.id, user.email)
        return jsonify({"access_token": token, "token_type": "bearer"})
    finally:
        db.close()

@app.get("/auth/validate")
def validate():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify({"error": "missing bearer token"}), 401

    token = auth.split(" ", 1)[1].strip()
    payload = decode_token(token)
    if not payload:
        return jsonify({"error": "invalid token"}), 401

    return jsonify({"user_id": int(payload["sub"]), "email": payload["email"]})
