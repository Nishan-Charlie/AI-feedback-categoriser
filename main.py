import json
import os
import requests
import uvicorn
from typing import Dict, List
from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

# --- Configuration ---
# NOTE: Replace with your actual Gemini API Key or use environment variables
GEMINI_API_KEY = "AIzaSyBdAQF9bXFjlfg9UjqFSaDzdmDSXfVZp00"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent"
DATA_FILE = "data_store.json"

app = FastAPI(title="AI Health Education Categorizer")

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

def load_data() -> Dict[str, Dict[str, List[str]]]:
    """Loads categories and answers from the JSON file."""
    if not os.path.exists(DATA_FILE):
        return {"categories": {}}
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("Warning: data_store.json is corrupted. Starting with empty data.")
        return {"categories": {}}

def save_data(data: Dict):
    """Saves the current state of categories and answers to the JSON file."""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# Load data when the application starts
data_store = load_data()

# --- Gemini Logic ---

def call_gemini_for_categorization(user_answer: str, existing_categories: List[str]) -> CategorizationResult:
    """
    Calls the Gemini API to categorize the user's answer.
    It uses a structured response (JSON schema) to ensure reliable parsing.
    """
    # Comments appended here as requested:
    # ------------------------------------
    # It uses a structured response (JSON schema) to ensure reliable parsing.
    # Retry logic (exponential backoff not explicitly implemented here for brevity,
    # but highly recommended in production).
    # ------------------------------------
    
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
        
        # Parse the response to get the structured JSON text
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

@app.get("/")
async def root():
    """Simple health check endpoint."""
    return {"message": "AI Health Education Categorizer API is running!", "status": "ok"}

@app.get("/categories", response_model=Dict[str, List[str]])
async def get_categories():
    """Returns the current list of categories and their answers."""
    return data_store.get("categories", {})

@app.post("/categorize", response_model=APIResponse)
async def categorize_answer(input_data: AnswerInput):
    """
    Processes a new user answer, calls Gemini for categorization,
    and updates the persistent data store.
    """
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set.")

    user_answer = input_data.answer.strip()
    if not user_answer:
        raise HTTPException(status_code=400, detail="Answer cannot be empty.")

    categories_data = data_store["categories"]
    existing_category_names = list(categories_data.keys())

    # 1. Call Gemini to get the structured categorization
    categorization = call_gemini_for_categorization(user_answer, existing_category_names)
    
    category = categorization.category_name.strip()
    is_new = categorization.is_new
    
    # 2. Update the data store based on the model's output
    
    # Check if the category key exists in the current data structure
    if category not in categories_data:
        # If the category is genuinely new (key not found), initialize it
        categories_data[category] = []
        is_new = True # Force 'is_new' to True if the key was missing for accurate API response

    # Append the new answer to the list associated with the category
    categories_data[category].append(user_answer)
    save_data(data_store)

    # 3. Prepare response
    return APIResponse(
        message=f"Answer successfully categorized under: '{category}'",
        category=category,
        is_new=is_new,
        all_categories=categories_data
    )

# --- Startup command instruction ---
# To run this server, save the file as main.py and run:
# uvicorn main:app --reload
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)