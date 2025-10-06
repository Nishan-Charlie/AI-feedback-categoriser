import json
import os
import requests
import uvicorn
import secrets
import csv
from typing import Dict, List
from fastapi import Query
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

# --- Configuration ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBdAQF9bXFjlfg9UjqFSaDzdmDSXfVZp00")
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent"
DATA_FILE = "data_store.json"
QUESTIONS_FILE = "questions.json"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

app = FastAPI(title="AI Health Education Categorizer")
templates = Jinja2Templates(directory=".")

# In-memory session management (replace with a more robust solution for production)
sessions = {}

# Allow the frontend (index.html) to communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for simplicity in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---

class AnswerInput(BaseModel):
    """Input model for the user's open-ended answer."""
    answer: str = Field(..., description="The user's response to the AI in health sciences education question.")
    question: str | None = Field(None, description="The question this answer is responding to.")

class CategorizationResult(BaseModel):
    """Expected structured output from the Gemini model."""
    category_name: str = Field(..., description="The determined category name.")
    is_new: bool = Field(..., description="True if a new category was created, False otherwise.")

class APIResponse(BaseModel):
    """Standard API response for categorization."""
    message: str
    category: str
    is_new: bool
    all_categories: Dict[str, List[str]]

# --- Data Persistence Functions ---

def load_data() -> Dict:
    """Loads data from the JSON file and migrates to presentations model if needed.

    Target schema:
    {
      "presentations": {
        "default": {
          "categories_by_question": {
            "Question text": { category: [answers] }
          }
        }
      }
    }
    """
    if not os.path.exists(DATA_FILE):
        return {"presentations": {"default": {"categories_by_question": {}}}}
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print("Warning: data_store.json is corrupted. Starting with empty data.")
        return {"presentations": {"default": {"categories_by_question": {}}}}

    # Migrate older schema {"categories": {...}} → presentations.default.categories_by_question["General"]
    if isinstance(data, dict) and "presentations" not in data:
        categories = data.get("categories", {}) if isinstance(data, dict) else {}
        data = {"presentations": {"default": {"categories_by_question": {"General": categories}}}}

    # Ensure required keys
    data.setdefault("presentations", {})
    data["presentations"].setdefault("default", {"categories_by_question": {}})
    data["presentations"]["default"].setdefault("categories_by_question", {})

    # Further migrate from presentations.default.categories → categories_by_question.General if present
    default_p = data["presentations"].get("default", {})
    if "categories" in default_p and isinstance(default_p.get("categories"), dict):
        existing = default_p.get("categories", {})
        cbq = default_p.setdefault("categories_by_question", {})
        if "General" not in cbq:
            cbq["General"] = existing
        del default_p["categories"]
    return data

def save_data(data: Dict):
    """Saves the current state of categories and answers to the JSON file."""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_questions() -> Dict[str, List[str]]:
    """Loads questions per presentation from the JSON file, migrating if needed.

    Target schema: { presentationName: [questions] }
    """
    if not os.path.exists(QUESTIONS_FILE):
        return {"default": []}
    try:
        with open(QUESTIONS_FILE, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print("Warning: questions.json is corrupted. Starting with empty data.")
        return {"default": []}

    # Migrate from list → {"default": list}
    if isinstance(data, list):
        return {"default": data}
    if isinstance(data, dict):
        data.setdefault("default", [])
        return data
    return {"default": []}

def save_questions(questions_by_presentation: Dict[str, List[str]]):
    """Saves the current state of questions per presentation to the JSON file."""
    with open(QUESTIONS_FILE, 'w') as f:
        json.dump(questions_by_presentation, f, indent=2)

# Load data when the application starts
data_store = load_data()
questions_store = load_questions()

# --- Gemini Logic ---

def call_gemini_for_categorization(user_answer: str, existing_categories: List[str]) -> CategorizationResult:
    """
    Calls the Gemini API to categorize the user's answer.
    It uses a structured response (JSON schema) to ensure reliable parsing.
    """
    current_categories_list = ", ".join(existing_categories)
    
    system_prompt = f"""You are an AI Categorization Engine for academic interests. 
    Your task is to classify a user's open-ended answer about their interest in AI in health sciences education.
    
    Current existing categories are: {current_categories_list if existing_categories else 'None'}.
    
    RULES:
    1. If the user's answer strongly aligns with an EXISTING category, use that category name exactly.
    2. If the user's answer is unique and represents a NEW, distinct topic, create a CONCISE (2-4 word) and descriptive new category name.
    3. You MUST return your response in the specified JSON format.
    4. Set 'is_new' to true only if you propose a new category name.
    """
    
    user_query = f"User's interest: '{user_answer}'. Classify this interest."

    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "category_name": {"type": "STRING", "description": "The determined category name for the user's interest."},
                    "is_new": {"type": "BOOLEAN", "description": "True if the category_name is a new category, False if it is an existing one."}
                },
                "required": ["category_name", "is_new"]
            }
        }
    }

    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(f"{API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        json_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')

        if not json_text:
            raise ValueError("Gemini returned an empty or malformed JSON structure.")
        
        parsed_result = json.loads(json_text)
        return CategorizationResult(**parsed_result)

    except requests.exceptions.RequestException as e:
        print(f"API Request Error: {e}")
        raise HTTPException(status_code=500, detail="Error communicating with Gemini API.")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Response Parsing Error: {e}")
        print(f"Raw API response text: {response.text if 'response' in locals() else 'N/A'}")
        raise HTTPException(status_code=500, detail="Could not parse structured response from AI.")


# --- FastAPI Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "questions": questions_store})

# Convenience routes to ensure landing page resolves to index
@app.get("/index")
async def index_redirect():
    return RedirectResponse(url="/", status_code=307)

@app.get("/index.html")
async def index_html_redirect():
    return RedirectResponse(url="/", status_code=307)

@app.get("/visualize", response_class=HTMLResponse)
async def visualize_page(request: Request):
    return templates.TemplateResponse("visualize.html", {"request": request})

@app.get("/questions", response_model=List[str])
async def get_questions(p: str = Query("default", alias="p")):
    """Returns the list of questions for a presentation."""
    return questions_store.get(p, [])

@app.get("/categories", response_model=Dict[str, List[str]])
async def get_categories(p: str = Query("default", alias="p"), question: str = Query("General", alias="question")):
    """Returns categories and answers for a presentation and question."""
    presentation = data_store.get("presentations", {}).get(p)
    if not presentation:
        return {}
    return presentation.get("categories_by_question", {}).get(question, {})

@app.get("/categories_by_question")
async def get_categories_by_question(p: str = Query("default", alias="p")) -> Dict[str, Dict[str, List[str]]]:
    """Returns a mapping of question -> categories for a presentation."""
    presentation = data_store.get("presentations", {}).get(p)
    if not presentation:
        return {}
    return presentation.get("categories_by_question", {})

@app.post("/categorize", response_model=APIResponse)
async def categorize_answer(input_data: AnswerInput, p: str = Query("default", alias="p")):
    """
    Processes a new user answer, calls Gemini for categorization,
    and updates the persistent data store.
    """
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set.")

    user_answer = input_data.answer.strip()
    if not user_answer:
        raise HTTPException(status_code=400, detail="Answer cannot be empty.")

    # Ensure presentation exists
    presentations = data_store.setdefault("presentations", {})
    presentation = presentations.setdefault(p, {"categories_by_question": {}})
    categories_by_question = presentation.setdefault("categories_by_question", {})

    question_text = (input_data.question or "General").strip() or "General"
    categories_data = categories_by_question.setdefault(question_text, {})
    existing_category_names = list(categories_data.keys())

    categorization = call_gemini_for_categorization(user_answer, existing_category_names)
    
    category = categorization.category_name.strip()
    is_new = categorization.is_new
    
    if category not in categories_data:
        categories_data[category] = []
        is_new = True

    categories_data[category].append(user_answer)
    save_data(data_store)

    return APIResponse(
        message=f"Answer successfully categorized under: '{category}'",
        category=category,
        is_new=is_new,
        all_categories=categories_data
    )

# --- Admin Section ---

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        session_id = secrets.token_urlsafe(16)
        sessions[session_id] = {"authenticated": True}
        response = RedirectResponse(url="/admin", status_code=303)
        # Ensure cookie is scoped correctly and survives the redirect
        response.set_cookie(
            key="session_id",
            value=session_id,
            path="/",
            httponly=True,
            samesite="lax"
        )
        return response
    return RedirectResponse(url="/login", status_code=303)

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and sessions.get(session_id, {}).get("authenticated"):
        return templates.TemplateResponse("admin.html", {"request": request, "questions": questions_store})
    return RedirectResponse(url="/login", status_code=303)

# Handle trailing slash for admin as well
@app.get("/admin/")
async def admin_trailing_slash():
    return RedirectResponse(url="/admin", status_code=307)

@app.post("/admin/add_question")
async def add_question(request: Request, question: str = Form(...), p: str = Query("default", alias="p")):
    session_id = request.cookies.get("session_id")
    if not (session_id and sessions.get(session_id, {}).get("authenticated")):
        return RedirectResponse(url="/login", status_code=303)

    questions_for_presentation = questions_store.setdefault(p, [])
    questions_for_presentation.append(question)
    save_questions(questions_store)
    return RedirectResponse(url="/admin?p=" + p, status_code=303)

@app.get("/admin/download_csv")
async def download_csv(request: Request, p: str = Query("default", alias="p")):
    session_id = request.cookies.get("session_id")
    if not (session_id and sessions.get(session_id, {}).get("authenticated")):
        return RedirectResponse(url="/login", status_code=303)

    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Question', 'Category', 'Answer'])
    categories_by_question = data_store.get("presentations", {}).get(p, {}).get("categories_by_question", {})
    for q_text, categories in categories_by_question.items():
        for category, answers in categories.items():
            for answer in answers:
                writer.writerow([q_text, category, answer])
    
    return HTMLResponse(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=data.csv"})

@app.get("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id in sessions:
        del sessions[session_id]
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="session_id")
    return response

# --- Startup command instruction ---
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
