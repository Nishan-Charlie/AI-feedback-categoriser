# AI in Health Education Categorizer

This project is a web application that uses the Gemini API to categorize user interests in the field of AI in Health Sciences Education. Users can submit their interests through a web interface, and the application will intelligently categorize them, creating new categories as needed.

## Features

-   **Web-based Interface:** A simple and intuitive web UI for users to submit their interests.
-   **AI-Powered Categorization:** Leverages the Gemini API to understand and categorize user submissions.
-   **Dynamic Category Creation:** Automatically creates new categories when a user's interest doesn't fit into an existing one.
-   **Per-Presentation Mode:** Isolate sessions by slide/presentation using a `?p=YourSlideName` query parameter.
-   **Per-Question Categorization:** Each presentation can have multiple questions; categories and answers are tracked per question.
-   **Visualization Page:** A dedicated page shows bar charts of category counts per question.
-   **QR Code:** Home page shows a QR linking to the exact presentation URL for easy audience access.
-   **Data Persistence:** Stores categorized interests in JSON files.
-   **FastAPI Backend:** A robust and fast Python web framework for handling API requests.

## Technologies Used

-   **Frontend:** HTML, Tailwind CSS, JavaScript
-   **Backend:** Python, FastAPI, Uvicorn
-   **API:** Google Gemini
-   **Data Storage:** JSON

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Create a virtual environment and install dependencies:**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    # source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Set up your Gemini API Key (and optional admin password):**
    - Create a `.env` file in the project root with:
      ```env
      GEMINI_API_KEY=YOUR_API_KEY
      ADMIN_PASSWORD=admin
      ```

## Running

Start the FastAPI server (either command works):
```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
The app will be available at `http://localhost:8000`.

## Usage

- **Home (Audience input):**
  - URL: `http://localhost:8000/?p=YourSlideName`
  - Shows all questions for the presentation and lets users submit answers.
  - Displays per-question categories under each question.
  - Includes a QR code linking to the same URL for quick access.

- **Admin (Manage questions and export data):**
  - Login: `http://localhost:8000/login`
  - Admin panel: `http://localhost:8000/admin?p=YourSlideName`
  - Add questions per presentation and download categorized data as CSV (includes Question, Category, Answer).

- **Visualization (Charts):**
  - URL: `http://localhost:8000/visualize?p=YourSlideName`
  - Read-only view with per-question bar charts of category counts.

## API Overview

All endpoints accept a presentation query parameter `p` (default: `default`). Some endpoints also accept a `question` query parameter.

- `GET /questions?p=...` → returns `string[]`
- `GET /categories?p=...&question=...` → returns `{ [category: string]: string[] }`
- `POST /categorize?p=...` body:
  ```json
  { "answer": "text", "question": "Question text" }
  ```
  returns `{ message, category, is_new, all_categories }`
- `POST /admin/add_question?p=...` (form `question`)
- `GET /admin/download_csv?p=...` (CSV: Question, Category, Answer)

## Data Storage

- `data_store.json`
  - Schema:
    ```json
    {
      "presentations": {
        "YourSlideName": {
          "categories_by_question": {
            "Question text": {
              "Category A": ["answer 1", "answer 2"],
              "Category B": ["answer 3"]
            }
          }
        }
      }
    }
    ```
  - Legacy data is auto-migrated on startup to the new schema under `presentations.default`.

- `questions.json`
  - Schema: `{ "YourSlideName": ["Question 1", "Question 2"] }`
  - Legacy list format is auto-migrated to `{ "default": [...] }`.

## Notes

- Open pages via the FastAPI server URLs (e.g., `http://localhost:8000/`) so relative links like `/login` work correctly. Avoid opening `index.html` directly from disk.
- The admin session uses an in-memory cookie; restarting the server clears sessions.

## File Descriptions

-   `index.html`: Audience home UI (questions, inputs, per-question categories, QR code).
-   `visualize.html`: Read-only charts page (per-question categories).
-   `admin.html`: Admin panel to add questions and export data.
-   `main.py`: FastAPI application and routes.
-   `requirements.txt`: Python dependencies.
-   `data_store.json`: Categorized interests data store.
-   `questions.json`: Questions per presentation.
-   `.env`: Environment variables (API key, optional admin password).
-   `README.md`: This file.
