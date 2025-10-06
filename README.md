# AI in Health Education Categorizer

This project is a web application that uses the Gemini API to categorize user interests in the field of AI in Health Sciences Education. Users can submit their interests through a web interface, and the application will intelligently categorize them, creating new categories as needed.

## Features

-   **Web-based Interface:** A simple and intuitive web UI for users to submit their interests.
-   **AI-Powered Categorization:** Leverages the Gemini API to understand and categorize user submissions.
-   **Dynamic Category Creation:** Automatically creates new categories when a user's interest doesn't fit into an existing one.
-   **Data Persistence:** Stores categorized interests in a JSON file (`data_store.json`).
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
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3.  **Set up your Gemini API Key:**
    -   Create a `.env` file in the root of the project.
    -   Add your Gemini API key to the `.env` file as follows:
        ```
        GEMINI_API_KEY="YOUR_API_KEY"
        ```
    - In `main.py`, the line `GEMINI_API_KEY = "AIzaSyBdAQF9bXFjlfg9UjqFSaDzdmDSXfVZp00"` is a placeholder. For security, it's recommended to load the API key from the environment. You would modify `main.py` to use a library like `python-dotenv` to load the key from the `.env` file.

## Usage

1.  **Start the FastAPI server:**
    ```bash
    uvicorn main:app --reload
    ```
    The server will be running at `http://localhost:8000`.

2.  **Open the web interface:**
    -   Open the `index.html` file in your web browser.

3.  **Categorize your interests:**
    -   Enter your interest in the text area and click the "Categorize My Interest" button.
    -   The application will display the category for your interest and update the list of categorized interests.

## File Descriptions

-   **`index.html`:** The main HTML file for the web interface.
-   **`main.py`:** The FastAPI application that handles the backend logic and API requests.
-   **`requirements.txt`:** A list of Python dependencies for the project.
-   **`data_store.json`:** The JSON file where categorized interests are stored.
-   **`.env`:** A file for storing environment variables, such as the Gemini API key.
-   **`README.md`:** This file.
