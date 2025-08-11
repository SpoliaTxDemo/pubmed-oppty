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
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        # Check against the environment variables
        ok_user = username == os.getenv("DEMO_USERNAME", "admin")
        ok_pass = check_password_hash(os.getenv("DEMO_PASSWORD_HASH", ""), password)
        if ok_user and ok_pass:
            login_user(DemoUser())
            return redirect(url_for("search"))
        flash("Invalid credentials", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    """Logout the current user."""
    logout_user()
    return redirect(url_for("login"))


@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    """Display search form and handle PubMed searches."""
    pharma_options = ["Novartis", "Roche"]
    disease_options = RARE_METABOLIC_DEFAULT_TERMS
    if request.method == "POST":
        # Get selected affiliations and disease terms
        affs = request.form.getlist("affiliations")
        dterms = request.form.getlist("dterms")
        custom_terms = request.form.get("custom_terms", "")
        # Build PubMed query string
        query = build_query(affs, dterms, custom_terms)
        # Search PubMed for up to 100 PMIDs since 2005
        pmids = esearch_pmids(query, retmax=100, min_year=2005)
        # Fetch detailed records for PMIDs
        records = efetch_medline(pmids)
        # Save results to a temporary file for download
        text_blob = to_txt(records)
        export_path = f"/tmp/pubmed_export_{uuid.uuid4().hex}.txt"
        with open(export_path, "w", encoding="utf-8") as fh:
            fh.write(text_blob)
        # Store results in cache for analysis
        key = get_cache_key()
        CACHE[key] = {
            "records": records,
            "export_path": export_path,
            "query": query,
        }
        return render_template(
            "results.html",
            query=query,
            count=len(records),
            records=records,
            export_ready=True,
            models=ALLOWED_MODELS,
            default_model=DEFAULT_MODEL,
        )
    # GET request: render search form with defaults
    return render_template(
        "search.html",
        pharma_options=pharma_options,
        disease_options=disease_options,
    )


@app.route("/download")
@login_required
def download():
    """Download the most recent search results as a text file."""
    key = get_cache_key()
    item = CACHE.get(key)
    if not item or not os.path.exists(item["export_path"]):
        flash("No export available. Run a search first.", "error")
        return redirect(url_for("search"))
    return send_file(
        item["export_path"], as_attachment=True, download_name="pubmed_results.txt"
    )


@app.route("/analyze", methods=["POST"])
@login_required
def analyze():
    """Run OpenAI analysis on the cached abstracts."""
    key = get_cache_key()
    item = CACHE.get(key)
    if not item:
        flash("No results to analyze. Run a search first.", "error")
        return redirect(url_for("search"))
    # Read user-selected model or use default
    model = request.form.get("model", DEFAULT_MODEL)
    # Combine abstracts into a single text snippet
    text_blob = to_txt(item["records"])
    # Call OpenAI analysis
    analysis = analyze_abstracts(text_blob, model=model)
    return render_template(
        "analysis.html", query=item.get("query", ""), analysis=analysis, model=model
    )


if __name__ == "__main__":
    # Run the app for local development
    app.run(debug=True, port=5000)