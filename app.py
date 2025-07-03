from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import requests
import os
import json
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

import fitz  # PyMuPDF
from csv import reader


def extract_text_from_image(path):
    results = reader.readtext(path)
    return '\n'.join([text for _, text, _ in results])

load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecret")

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_ID = "deepseek/deepseek-chat:free"
USER_FILE = "registered_users.json"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ------------------- Utility Functions -------------------
def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(users, f, indent=2)

def deepseek_response(prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1000
    }
    try:
        resp = requests.post(url, headers=headers, json=data)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        return f"Error: {resp.json()}"
    except Exception as e:
        return f"Exception occurred: {str(e)}"

def add_language_instruction(prompt, language):
    lang_instruction = {
        "english": "Respond in English.",
        "assamese": "Respond in Assamese.",
        "hindi": "Respond in Hindi.",
        "marathi": "Respond in Marathi."
    }
    return f"{prompt.strip()}\n\n{lang_instruction.get(language.lower(), '')}"

def extract_text_from_pdf(path):
    text = ""
    with fitz.open(path) as doc:
        for page in doc:
            text += page.get_text()
    return text.strip()

# ------------------- Routes -------------------
@app.route("/register-user", methods=["POST"])
def register_user():
    data = request.get_json()
    email, name, password = data.get("email"), data.get("name"), data.get("password")
    photo = data.get("photo", "")

    if not all([email, name, password]):
        return jsonify({"error": "Missing required fields"}), 400

    users = load_users()
    if email in users:
        return jsonify({"error": "User already exists"}), 409

    users[email] = {"name": name, "password": password, "photo": photo}
    save_users(users)
    return jsonify({"message": "Registration successful"}), 200

@app.route("/manual-login", methods=["POST"])
def manual_login():
    data = request.get_json()
    email, password = data.get("email"), data.get("password")

    users = load_users()
    user = users.get(email)
    if user and user["password"] == password:
        session.update({
            "authenticated": True,
            "user": email,
            "user_name": user["name"],
            "user_pic": user.get("photo", "")
        })
        return jsonify({"message": "Login successful"}), 200

    return jsonify({"error": "Invalid credentials"}), 401

@app.route("/session-login", methods=["POST"])
def session_login():
    data = request.get_json()
    email = data.get("email")

    users = load_users()
    if email in users:
        user = users[email]
        session.update({
            "authenticated": True,
            "user": email,
            "user_name": user["name"],
            "user_pic": user.get("photo", "")
        })
        return jsonify({"message": "Session set"}), 200

    return jsonify({"error": "Not registered"}), 401

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))

@app.route("/")
def landing():
    return render_template("home1.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/home")
def home():
    if not session.get("authenticated"):
        return redirect(url_for("landing"))
    return render_template("home.html", user=session["user"], name=session["user_name"], photo=session.get("user_pic"))

# ------------------- DeepSeek AI Tools -------------------
@app.route("/generate-content", methods=["GET", "POST"])
def generate_content():
    if not session.get("authenticated"):
        return redirect(url_for("landing"))

    result = None
    if request.method == "POST":
        prompt = request.form["prompt"]
        language = request.form["language"]
        full_prompt = add_language_instruction(
            f"You are an educational AI assistant. Generate culturally relevant and age-appropriate content based on: {prompt}",
            language
        )
        result = deepseek_response(full_prompt)

    return render_template("content_generator.html", result=result)

@app.route("/generate-worksheet", methods=["GET", "POST"])
def generate_worksheet():
    if not session.get("authenticated"):
        return redirect(url_for("landing"))

    result = None
    if request.method == "POST":
        description = request.form["description"]
        language = request.form["language"]
        full_prompt = add_language_instruction(
            f"Generate a worksheet from the following topic or textbook photo description, with variations for different grade levels: {description}",
            language
        )
        result = deepseek_response(full_prompt)

    return render_template("worksheet_generator.html", result=result)

@app.route("/knowledge-base", methods=["GET", "POST"])
def knowledge_base():
    if not session.get("authenticated"):
        return redirect(url_for("landing"))

    result = None
    if request.method == "POST":
        question = request.form["question"]
        language = request.form["language"]
        full_prompt = add_language_instruction(
            f"Explain this question in simple terms like you are teaching a child. Include analogies if helpful: {question}",
            language
        )
        result = deepseek_response(full_prompt)

    return render_template("knowledge_base.html", result=result)

@app.route("/visual-aids", methods=["GET", "POST"])
def visual_aids():
    if not session.get("authenticated"):
        return redirect(url_for("landing"))

    result = None
    if request.method == "POST":
        description = request.form["description"]
        language = request.form["language"]
        full_prompt = add_language_instruction(
            f"Respond ONLY with valid Mermaid syntax (e.g., graph TD) to illustrate this concept. Do NOT use code blocks or triple backticks: {description}",
            language
        )
        result = deepseek_response(full_prompt)

    return render_template("visual_aids.html", result=result)

@app.route("/quiz_generator", methods=["GET", "POST"])
def quiz_generator():
    if not session.get("authenticated"):
        return redirect(url_for("landing"))

    result = None
    if request.method == "POST":
        selected_class = request.form["class"]
        subject = request.form["subject"]
        topic = request.form["topic"]
        language = request.form["language"]
        full_prompt = add_language_instruction(
            f"Generate a quiz for Class {selected_class} students on the topic '{topic}' from the subject '{subject}'. Include MCQs and short answer questions.",
            language
        )
        result = deepseek_response(full_prompt)

    return render_template("quiz_generator.html", result=result)

# ------------------- Run App -------------------
if __name__ == "__main__":
    app.run(debug=True)
