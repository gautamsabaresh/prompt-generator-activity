# Prompt Generator Essay Feedback

This project is a Streamlit-based web application designed to help generate tailored prompts for student writing tasks. It allows you to define prompt templates, fetch dynamic content from a JSON API, input student answers (single or batch via CSV), and generate feedback prompts accordingly.

## Features
- Define and edit prompt templates with variable placeholders
- Fetch and populate variables from a remote JSON content URL
- Input student answers via text box or CSV upload
- Generate and download prompts for each student answer

## Prerequisites
- Python 3.8+
- [Poetry](https://python-poetry.org/) for dependency management

## Installation
1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd prompt-generator-essay-feedback
   ```
2. **Install dependencies using Poetry:**
   ```bash
   poetry install
   ```

## Running the App
1. **Start the Streamlit app using Poetry:**
   ```bash
   poetry run streamlit run main.py
   ```
2. Open the provided local URL in your browser to use the app.

## Usage
- Define your prompt template using the provided variables.
- Fetch content from a JSON API to populate template variables.
- Input student answers directly or upload a CSV file.
- Generate and review feedback prompts, and download them as CSV if needed.

---

Feel free to customize the template and extend the app as needed for your workflow.
