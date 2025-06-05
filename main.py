import streamlit as st
import re
import pandas as pd
import json # For handling JSON data from URL
import requests # For making HTTP requests

# --- Predefined list of allowed variables ---
# Note: {{student_answer}} is special and comes from the Answers input section.
PREDEFINED_VARIABLES = [
    "task_instruction",
    "vocabulary_list",
    "grammar_reference",
    "communication_reference",
    "guiding_questions",
    "can_do_statements"
]
ALL_POSSIBLE_VARIABLES = PREDEFINED_VARIABLES + ["student_answer"]

# --- Function to fetch data from URL and populate variables ---
def fetch_and_populate_variables_action(content_url):
    """
    Fetches data from content_url, parses the JSON, extracts relevant fields,
    and populates the predefined variable input fields in the UI.
    """
    # Reset or initialize fetched_variable_values in session state
    st.session_state.fetched_variable_values = {var: "" for var in PREDEFINED_VARIABLES} 

    if not content_url:
        st.warning("Please enter a Content URL to fetch variables.")
        return False

    st.info(f"Fetching data from: {content_url}...")
    try:
        response = requests.get(content_url, timeout=10) # 10-second timeout
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        activity_data = response.json()

        # Initialize local variables for extracted data
        task_instruction_val = ""
        vocabulary_list_str = ""
        grammar_reference_val = ""
        communication_reference_val = ""
        guiding_questions_val = ""
        can_do_statements_val = ""

        # Extract from interactions (for task_instruction and can_do_statements)
        interactions = activity_data.get('interactions', [])
        if interactions and isinstance(interactions, list) and len(interactions) > 0:
            interaction = interactions[0] 
            if isinstance(interaction, dict):
                task_instruction_val = interaction.get('instruction', '')
                
                can_do_statement_list_raw = interaction.get('canDoStatement', [])
                if isinstance(can_do_statement_list_raw, list):
                    can_do_statement_list = [
                        stmt.get('statement', '') 
                        for stmt in can_do_statement_list_raw if isinstance(stmt, dict) and stmt.get('statement')
                    ]
                    can_do_statements_val = "\n".join(f"- {s}" for s in can_do_statement_list)
        else:
            st.warning("Could not find 'interactions' array or it's empty/invalid in the JSON response.")

        # Extract from referenceScreens
        reference_screens = activity_data.get('referenceScreens', [])
        if isinstance(reference_screens, list):
            vocabulary_items_list = [] 
            for ref in reference_screens:
                if isinstance(ref, dict):
                    category = ref.get('category')
                    contents = ref.get('contents')
                    if isinstance(contents, dict):
                        if category == 'vocabulary':
                            vocab_list_from_json = contents.get('vocabularyList', [])
                            if isinstance(vocab_list_from_json, list):
                                vocabulary_items_list.extend(str(item) for item in vocab_list_from_json if item)
                        elif category == 'grammar':
                            grammar_reference_val = contents.get('reference', '')
                        elif category == 'communication':
                            communication_reference_val = contents.get('reference', '')
            if vocabulary_items_list:
                vocabulary_list_str = ', '.join(vocabulary_items_list)
        else:
            st.warning("Could not find 'referenceScreens' array in the JSON response or it's not a list.")

        # Extract from secondaryScreens (for guiding_questions)
        secondary_screens = activity_data.get('secondaryScreens', [])
        if isinstance(secondary_screens, list):
            guiding_questions_list_raw = []
            for screen in secondary_screens:
                if isinstance(screen, dict):
                    secondary_content_items = screen.get('contents', [])
                    if isinstance(secondary_content_items, list):
                        for item in secondary_content_items:
                            if isinstance(item, dict):
                                question_text = item.get('secondaryContent')
                                if question_text: 
                                    guiding_questions_list_raw.append(str(question_text))
            if guiding_questions_list_raw:
                guiding_questions_val = "\n".join(f"- {q}" for q in guiding_questions_list_raw)
        else:
            st.warning("Could not find 'secondaryScreens' array in the JSON response or it's not a list.")

        # Populate session state with extracted values
        st.session_state.fetched_variable_values['task_instruction'] = task_instruction_val
        st.session_state.fetched_variable_values['vocabulary_list'] = vocabulary_list_str
        st.session_state.fetched_variable_values['grammar_reference'] = grammar_reference_val
        st.session_state.fetched_variable_values['communication_reference'] = communication_reference_val
        st.session_state.fetched_variable_values['guiding_questions'] = guiding_questions_val
        st.session_state.fetched_variable_values['can_do_statements'] = can_do_statements_val
        
        st.success("Successfully fetched and processed data from URL.")
        return True

    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching URL: {e}")
    except json.JSONDecodeError as e:
        st.error(f"Error parsing JSON response: {e}")
    except KeyError as e:
        st.error(f"Error accessing expected key in JSON data: {e}. Please check JSON structure.")
    except Exception as e:
        st.error(f"An unexpected error occurred during fetch: {e}")
    
    # Ensure variables are at least initialized to empty if fetch fails
    for var_name in PREDEFINED_VARIABLES:
        if var_name not in st.session_state.fetched_variable_values: # Check if key exists
             st.session_state.fetched_variable_values[var_name] = ""
        elif st.session_state.fetched_variable_values[var_name] is None: # Check if value is None
             st.session_state.fetched_variable_values[var_name] = ""
    return False


# --- Main prompt generation logic ---
def generate_prompt_action(prompt_template, variable_values_from_fetch, content_url, answers_input, answers_method):
    """
    Processes the inputs to generate the final prompt(s) and displays them.
    """
    # Initialize a dictionary for all variables that will go into the template
    all_vars_for_template = {key: variable_values_from_fetch.get(key, "") for key in PREDEFINED_VARIABLES}

    # Check for non-allowed variables in the template early
    template_vars_in_use = set(re.findall(r"\{\{(.*?)\}\}", prompt_template))
    allowed_vars_set = set(ALL_POSSIBLE_VARIABLES)
    non_allowed_vars = template_vars_in_use - allowed_vars_set
    if non_allowed_vars:
        st.warning(f"Warning: The template uses variables not in the predefined list: {', '.join(non_allowed_vars)}")

    final_prompts_generated_data = [] # To store data for potential CSV download

    if answers_method == "Text Box (for a single answer)":
        current_student_answer = answers_input if answers_input else ""
        if not current_student_answer and "student_answer" in template_vars_in_use:
            st.info("Note: 'student_answer' is in the template, but no answer was provided in the text box.")
        
        all_vars_for_template["student_answer"] = current_student_answer
        
        final_prompt = prompt_template
        for var_key, var_value in all_vars_for_template.items():
            if var_key in ALL_POSSIBLE_VARIABLES: # Ensure we only try to replace allowed variables
                final_prompt = final_prompt.replace(f"{{{{{var_key}}}}}", str(var_value))
        
        st.markdown("#### Generated Prompt (with Text Box Answer):")
        st.code(final_prompt, language='text')
        final_prompts_generated_data.append({
            # "original_student_answer": current_student_answer, 
            "generated_prompt": final_prompt
        })

    elif answers_method == "Upload CSV (for multiple answers)":
        if answers_input and isinstance(answers_input, list):
            st.markdown(f"#### Generating Prompts for {len(answers_input)} Answers from CSV:")
            
            for student_answer_from_csv in answers_input:
                # Create a fresh copy of variables for each row to avoid modification issues
                current_row_vars = all_vars_for_template.copy()
                current_row_vars["student_answer"] = student_answer_from_csv

                current_filled_prompt = prompt_template
                for var_key, var_value in current_row_vars.items():
                    if var_key in ALL_POSSIBLE_VARIABLES:
                        current_filled_prompt = current_filled_prompt.replace(f"{{{{{var_key}}}}}", str(var_value))
                
                final_prompts_generated_data.append({
                    # "original_student_answer": student_answer_from_csv,
                    "generated_prompt": current_filled_prompt
                })
            
            if final_prompts_generated_data:
                results_df = pd.DataFrame(final_prompts_generated_data)
                st.dataframe(results_df, use_container_width=True)
                
                csv_output = results_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Generated Prompts as CSV",
                    data=csv_output,
                    file_name="generated_prompts.csv",
                    mime="text/csv",
                    key="download_csv_button"
                )
        elif not answers_input: # Covers None or empty list
             st.warning("CSV method selected, but no answers were processed from the CSV file for {{student_answer}}.")
        else: # Should not be reached if answers_input is None or list
            st.info("No answers extracted from the CSV file for {{student_answer}}.")
    else:
        st.error("Invalid answer method selected or no answers provided for processing.") # Should ideally not happen

    if not final_prompts_generated_data:
        st.info("No prompts were generated. Check inputs and template.")
    
    st.success("🚀 Prompt processing complete! Review generated prompts above. 🚀")


def run_ui():
    st.set_page_config(layout="wide", page_title="Prompt Engineering Assistant")
    
    # Initialize session state variables if they don't exist
    default_template = """You are a professional English teacher. An English language student has submitted a short writing task. Your job is to:

1. **Provide a corrected version** of the student’s text. Please highlight in bold font any text that you change.
2. **Evaluate the grammar**, also acknowledge usage of grammar given below that they're learning from the current lesson:🔍 "{{grammar_reference}}" Please use the same grammar terminology as is used in this grammar reference.
3. **Highlight any correct use of this grammar**, with examples from the student's text (if any).
4. **Identify any general grammar mistakes**, and suggest how to fix them (if any).
5. **Appreciate good use of vocabulary**, also acknowledge/suggest usage of the following vocabulary while giving feedback (if any): 📚 {{vocabulary_list}}
6. **Appreciate good use of communication phrases** acknowledge/suggest usage of the following communication phrases while giving feedback (if any): "{{communication_reference}}"
7. **Comment on the overall writing quality** — organization, punctuation, clarity, tone of voice, etc.
8. **Give constructive feedback** about how well the student completed the specific task instruction, with specific examples and tips for improvement.

The user at ***A1*** on the CEFR scale. When giving your feedback, do not use language with the user that is more complex than a language learner at ***A1*** level on the CEFR scale can understand.
Only provide corrections or examples of language structures that a language learner at ***A1*** level would be expected to be able to produce.
Do not provide corrections or examples of language structures that a language learner at ***A1*** level would not be expected to be able to produce.

---

### 📝 Task Instruction:
{{task_instruction}}

---

### 💬 Guiding Instruction/Questions:
{{guiding_questions}}

---

### ✍️ Student Response:
{{student_answer}}

---

### ✅ Can-Do Goals:
{{can_do_statements}}

---

🔁 Please follow one of the two feedback formats based on the student's response:

**If the student's response is a complete attempt** (e.g. a few meaningful sentences or a paragraph), use this structure:

**✍️ Your text corrected:**

**✅ What you did well:**  
Mention strong points (grammar used correctly, vocabulary, overall tone or structure, how well they completed the specific task).

**❌ What could be improved:**  
List grammar, vocabulary, structure, organization or tone of voice issues and how to fix them.

**💡 Suggestions:**  
Offer 1–2 concrete ideas to make this writing better. Finish with an encouraging comment for the student.

---

**If the student's response is too short or incomplete** (e.g. only a word or two, like "Hi" or "A"), respond with a short, encouraging note.  
Let them know the answer is too brief to evaluate properly, and suggest they rewrite it with reference to the task instructions and guiding questions.

--

🧠 Do **not** ask the student to reply or continue the conversation.  
Just give your feedback and end your response.
    """
    if 'prompt_template' not in st.session_state:
        st.session_state.prompt_template = default_template
    if 'content_url' not in st.session_state:
        st.session_state.content_url = "" 
    if 'fetched_variable_values' not in st.session_state:
        st.session_state.fetched_variable_values = {var: "" for var in PREDEFINED_VARIABLES}
    if 'answer_input_method' not in st.session_state:
        st.session_state.answer_input_method = "Text Box (for a single answer)"
    if 'single_answer' not in st.session_state:
        st.session_state.single_answer = ""
    if 'uploaded_csv_answers' not in st.session_state:
        st.session_state.uploaded_csv_answers = None # List of answers from CSV
    if 'last_uploaded_filename' not in st.session_state:
        st.session_state.last_uploaded_filename = None


    st.title("🛠️ Prompt Engineering Assistant")
    st.markdown("Define templates, fetch oscar activity content via URL, provide student answers, and generate tailored prompts.")
    st.markdown("---")
    
    # --- 1. Define Prompt Template ---
    st.subheader("1. Define Your Prompt Template")
    st.markdown(f"Use predefined variables: `{{{{{', '.join(ALL_POSSIBLE_VARIABLES)}}}}}`. Your inputs below will populate these.")
    # The key ensures that Streamlit updates st.session_state.prompt_template as the user types.
    st.session_state.prompt_template = st.text_area(
        label="Prompt Template String:",
        value=default_template,
        height=400,
        placeholder="Enter your prompt template here...",
        key="prompt_template_input_area",
        help="Enter your base user prompt. Values for variables will be filled from the sections below."
    )
    st.markdown("---")

    # --- 2. Fetch Dynamic Content for Variables ---
    st.subheader("2. Fetch Content for Template Variables")
    content_url_col, fetch_button_col = st.columns([3, 1])
    with content_url_col:
        st.session_state.content_url = st.text_input(
            "Content URL (expects JSON data):",
            value=st.session_state.content_url,
            key="content_url_input_field",
            placeholder="oscar api URL that returns JSON data",
            help="URL that returns a JSON object. Data from this URL will populate the 'Fetched Content Variables' section."
        )
    with fetch_button_col:
        # Add some vertical space to align button better if needed, or rely on Streamlit's default
        st.write("") # Creates a bit of space above the button
        if st.button("Fetch & Populate Variables", key="fetch_button", help="Fetch data from the URL to populate variables below.", use_container_width=True):
            fetch_and_populate_variables_action(st.session_state.content_url)
            # Streamlit reruns, and the variable fields below will pick up new session_state values.

    with st.expander("📝 Fetched Content Variables (Editable)", expanded=True):
        st.markdown("_These fields are populated from the Content URL. You can manually edit them before generating the final prompt._")
        
        # Ensure fetched_variable_values is a dictionary in session state
        if not isinstance(st.session_state.fetched_variable_values, dict):
            st.session_state.fetched_variable_values = {var: "" for var in PREDEFINED_VARIABLES}

        for var_name in PREDEFINED_VARIABLES:
            # Read current value from session_state to display
            current_var_value = st.session_state.fetched_variable_values.get(var_name, "")
            # Update session_state directly as user types due to the key
            st.session_state.fetched_variable_values[var_name] = st.text_area(
                f"`{var_name}`:",
                value=current_var_value,
                key=f"fetched_var_input_{var_name}", # Unique key for each text area
                height=100, 
                help=f"Value for {var_name}. Fetched from URL or manually entered."
            )
    st.markdown("---")

    # --- 3. Student Answer Input ---
    st.subheader("3. Provide Student's Answer(s)")
    st.markdown("This input will populate the `{{student_answer}}` variable in your template.")

    answer_options = ("Text Box (for a single answer)", "Upload CSV (for multiple answers)")
    # Get current index for radio button
    try:
        current_answer_method_index = answer_options.index(st.session_state.answer_input_method)
    except ValueError:
        current_answer_method_index = 0 # Default to first option if state is somehow invalid
        st.session_state.answer_input_method = answer_options[0]


    st.session_state.answer_input_method = st.radio(
        "How do you want to provide the student's answer(s)?",
        options=answer_options,
        index=current_answer_method_index,
        key="answer_method_radio_group",
        horizontal=True 
    )

    if st.session_state.answer_input_method == answer_options[0]: # Text Box
        st.session_state.single_answer = st.text_area(
            "Student's Answer (for `{{student_answer}}`):",
            # value=st.session_state.single_answer, # Read from session state
            height=150,
            key="single_answer_text_area_input", # Unique key
            help="This text will be used for the {{student_answer}} variable."
        )
        # Clear CSV state if user switches to text box
        if st.session_state.uploaded_csv_answers is not None:
            st.session_state.uploaded_csv_answers = None
            st.session_state.last_uploaded_filename = None
            # st.experimental_rerun() # Optional: force rerun if clearing state needs immediate UI update beyond widget
    
    else: # Upload CSV
        uploaded_file = st.file_uploader(
            "Upload CSV. Header must include 'Answers' (for `{{student_answer}}`).",
            type=['csv'],
            key="csv_file_uploader_widget" # Unique key
        )
        if uploaded_file is not None:
            # Process file only if it's new or different
            if uploaded_file.name != st.session_state.get('last_uploaded_filename', None):
                st.session_state.last_uploaded_filename = uploaded_file.name
                try:
                    df = pd.read_csv(uploaded_file)
                    if "Answers" in df.columns:
                        st.session_state.uploaded_csv_answers = df["Answers"].astype(str).tolist()
                        st.success(f"Successfully read {len(st.session_state.uploaded_csv_answers)} answers from '{uploaded_file.name}'.")
                        st.dataframe(df[["Answers"]].head(), height=150, use_container_width=True)
                    else:
                        st.error("CSV file is missing the required 'Answers' column. Please check the header.")
                        st.session_state.uploaded_csv_answers = None # Clear if error
                        st.session_state.last_uploaded_filename = None # Invalidate if error
                except Exception as e:
                    st.error(f"Error processing CSV file: {e}")
                    st.session_state.uploaded_csv_answers = None
                    st.session_state.last_uploaded_filename = None
            # If file is same as last, uploaded_csv_answers from session_state is already set
            elif st.session_state.uploaded_csv_answers:
                 st.info(f"Using previously uploaded file: '{st.session_state.last_uploaded_filename}'. Contains {len(st.session_state.uploaded_csv_answers)} answers.")

        elif st.session_state.last_uploaded_filename is not None: # File uploader is now empty, but there was a file
            st.info("CSV uploader is empty. Any previously uploaded CSV data has been cleared.")
            st.session_state.uploaded_csv_answers = None
            st.session_state.last_uploaded_filename = None
        
        # Clear single answer state if user switches to CSV
        if st.session_state.single_answer:
             st.session_state.single_answer = ""
             # st.experimental_rerun() # Optional

    st.markdown("---")

    # --- 4. Generate Final Prompt(s) ---
    st.subheader("4. Generate Final Prompt(s)")
    if st.button("🚀 Process & Generate Prompts", type="primary", use_container_width=True, key="generate_final_prompt_button"):
        # Determine the source of student answers based on the radio button selection
        answers_payload = None
        if st.session_state.answer_input_method == answer_options[0]:
            answers_payload = st.session_state.single_answer
        else: # CSV
            answers_payload = st.session_state.uploaded_csv_answers # This will be a list or None

        # Display collected info and generated prompts in an expander
        with st.expander("✨ Generated Prompts & Debug Information ✨", expanded=True):
            st.markdown("#### Input Summary:")
            st.markdown(f"**Content URL:** `{st.session_state.content_url if st.session_state.content_url else 'Not provided'}`")
            
            st.markdown("**Fetched Variable Values (used for generation):**")
            if st.session_state.fetched_variable_values:
                # Ensure all predefined keys exist for display, even if empty
                display_vars = {key: st.session_state.fetched_variable_values.get(key, "") for key in PREDEFINED_VARIABLES}
                vars_df = pd.DataFrame(display_vars.items(), columns=['Variable', 'Value'])
                st.table(vars_df)
            else:
                st.info("No variables were fetched/used from the content URL section.")

            st.markdown(f"**Answer Input Method:** `{st.session_state.answer_input_method}`")
            if st.session_state.answer_input_method == answer_options[0]:
                 st.markdown(f"**Student Answer (Text Box):** \n```\n{answers_payload if answers_payload else '(empty)'}\n```")
            elif st.session_state.uploaded_csv_answers:
                 st.markdown(f"**Student Answers (CSV):** {len(st.session_state.uploaded_csv_answers)} answers loaded.")


            st.markdown("---") # Separator before generated prompts
            generate_prompt_action(
                st.session_state.prompt_template,
                st.session_state.fetched_variable_values, # Pass the dictionary of fetched values
                st.session_state.content_url,
                answers_payload, # Pass the collected student answer(s)
                st.session_state.answer_input_method
            )
    st.markdown("---")


if __name__ == "__main__":
    run_ui()
