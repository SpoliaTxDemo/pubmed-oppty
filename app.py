# app.py
# Flask UI for the PubMed search app.
# Dependencies: flask, flask-login, python-dotenv, werkzeug, biopython
# pip install flask flask-login python-dotenv werkzeug biopython


import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from dotenv import load_dotenv
from pubmed_utils import (
build_query,
esearch_pmids,
efetch_medline,
to_txt,
RARE_METABOLIC_DEFAULT_TERMS,
TOP_20_PHARMA,
)
from analyze import analyze_abstracts


# Load environment variables from .env if present
load_dotenv()


# Create Flask app and configure secret key
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "change-me")


# Setup Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = "login"


# Allowed OpenAI models
ALLOWED_MODELS = ["gpt-4o-mini", "gpt-4o"]
DEFAULT_MODEL = ALLOWED_MODELS[0]


class DemoUser(UserMixin):
    """A simple user class for single-user authentication."""
    id = "demo"
    pass


@login_manager.user_loader
def load_user(user_id: str):
"""Load the single demo user if the ID matches."""
if user_id == "demo":
return DemoUser()
return None


# Session cache for storing search results temporarily
CACHE: dict[str, dict] = {}


def get_cache_key() -> str:
"""Retrieve or create a unique cache key for the current user session."""
if "cache_key" not in session:
session["cache_key"] = str(uuid.uuid4())
return session["cache_key"]


@app.route("/", methods=["GET"])
def home():
"""Home route redirects to the search page."""
return redirect(url_for("search"))


@app.route("/login", methods=["GET", "POST"])
def login():
"""Handle user login."""
app.run(debug=True, port=5000)
