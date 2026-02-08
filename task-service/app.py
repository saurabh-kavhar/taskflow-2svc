import os
from datetime import datetime

import requests
from flask import Flask, request, jsonify
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

# ==============================
# CONFIG
# ==============================

DATABASE_URL = os.getenv("DATABASE_URL")
AUTH_SERVICE_URL = os.getenv(
    "AUTH_SERVICE_URL",
    "http://auth-service:8000"
)

# ==============================
# DB SETUP
# ==============================

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    status = Column(String(50), default="todo")
    owner_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


# ==============================
# AUTH VALIDATION
# ==============================

def validate_token(auth_header: str):
    if not auth_header:
        return None

    try:
        r = requests.get(
            f"{AUTH_SERVICE_URL}/auth/validate",
            headers={"Authorization": auth_header},
            timeout=5,
        )

        if r.status_code != 200:
            return None

        return r.json()

    except requests.RequestException:
        return None


# ==============================
# APP INIT
# ==============================

app = Flask(__name__)

# ✅ Flask 3 safe startup init
with app.app_context():
    init_db()


# ==============================
# ROUTES
# ==============================

@app.get("/health")
def health():
    return {"ok": True}


@app.post("/tasks")
def create_task():
    auth = request.headers.get("Authorization", "")
    user = validate_token(auth)

    if not user:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()

    if not title:
        return jsonify({"error": "title required"}), 400

    db = SessionLocal()

    try:
        task = Task(
            title=title,
            owner_id=user["user_id"]
        )

        db.add(task)
        db.commit()
        db.refresh(task)

        return jsonify({
            "id": task.id,
            "title": task.title,
            "status": task.status
        })

    finally:
        db.close()


@app.get("/tasks")
def list_tasks():
    auth = request.headers.get("Authorization", "")
    user = validate_token(auth)

    if not user:
        return jsonify({"error": "unauthorized"}), 401

    db = SessionLocal()

    try:
        rows = (
            db.query(Task)
            .filter(Task.owner_id == user["user_id"])
            .order_by(Task.id.desc())
            .all()
        )

        return jsonify([
            {
                "id": r.id,
                "title": r.title,
                "status": r.status
            }
            for r in rows
        ])

    finally:
        db.close()


@app.patch("/tasks/<int:task_id>/status")
def update_status(task_id: int):
    auth = request.headers.get("Authorization", "")
    user = validate_token(auth)

    if not user:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True)
    status = (data.get("status") or "").strip()

    if status not in {"todo", "in_progress", "done"}:
        return jsonify({"error": "invalid status"}), 400

    db = SessionLocal()

    try:
        task = (
            db.query(Task)
            .filter(
                Task.id == task_id,
                Task.owner_id == user["user_id"]
            )
            .first()
        )

        if not task:
            return jsonify({"error": "task not found"}), 404

        task.status = status
        db.commit()

        return jsonify({
            "id": task.id,
            "status": task.status
        })

    finally:
        db.close()
