import streamlit as st
import requests
import json
import re
from datetime import datetime
import uuid
import os

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:5000")
API_BASE_URL = "https://llm-evaluation-api.mlcs.xyz"

# Initialize session state variables
if "step" not in st.session_state:
    st.session_state.step = 1
if "selected_eval" not in st.session_state:
    st.session_state.selected_eval = None
if "evaluation_data" not in st.session_state:
    st.session_state.evaluation_data = []
if "reviewer_id" not in st.session_state:
    st.session_state.reviewer_id = str(uuid.uuid4())
if "feedback_draft" not in st.session_state:
    st.session_state.feedback_draft = {}
if "page" not in st.session_state:
    st.session_state.page = 0
if "completed_models" not in st.session_state:
    st.session_state.completed_models = set()
if "models_per_page" not in st.session_state:
    st.session_state.models_per_page = 5

LIKERT_OPTIONS = {
    "Strongly Agree": 5,
    "Agree": 4,
    "Neutral": 3,
    "Disagree": 2,
    "Strongly Disagree": 1
}

LIKERT_OPTIONS2 = {
    "Expert: I am highly proficient, have in-depth knowledge, and use them frequently.": 5,
    "Advanced: I have extensive experience and use them regularly.": 4,
    "Intermediate: I have moderate experience; I understand key concepts and have used them in some projects.": 3,
    "Beginner: I have some basic understanding or have used them a few times.": 2,
    "No Experience: I have no experience with Domain Specific Languages.": 1
}

LIKERT_OPTIONS3 = {
    "Very Frequently: I use LLMs like ChatGPT daily or almost daily.": 5,
    "Frequently: I use LLMs like ChatGPT several times a week.": 4,
    "Occasionally: I use LLMs like ChatGPT monthly or a few times a month.": 3,
    "Rarely: I use LLMs like ChatGPT a few times a year or less.": 2,
    "Never: I never use LLMs like ChatGPT.": 1
}

# Helper functions for state management
def extract_prompt_from_description(description):
    match = re.search(r"<prompt>(.*?)</prompt>", description, re.DOTALL)
    if match:
        return match.group(1).strip()
    return description.strip()

def go_to_step(step_number):
    st.session_state.step = step_number
    st.rerun()

def extract_concepts(text):
    matches = re.findall(r'\bconcept\s+(\w+)', text, re.IGNORECASE)
    matches += re.findall(r'\bmain concept\s+(\w+)', text, re.IGNORECASE)
    return list(set(matches))

def save_draft():
    if not os.path.exists("feedback_data"):
        os.makedirs("feedback_data")
    filename = f"feedback_data/draft_{st.session_state.selected_eval}_{st.session_state.reviewer_id}.json"
    with open(filename, "w") as f:
        json.dump(st.session_state.feedback_draft, f, indent=2)

def submit_feedback():
    completed = [resp for resp in st.session_state.feedback_draft.get("responses", [])
                 if all(resp.get(k) for k in ["semantic", "concept", "complete", "advanced"])]
    if not completed:
        st.warning("No completed responses to submit.")
        return False
    
    payload = {
        "evaluation_id": st.session_state.selected_eval,
        "reviewer_info": st.session_state.feedback_draft.get("reviewer_info", {}),
        "responses": completed
    }
    try:
        res = requests.post(f"{API_BASE_URL}/submit_feedback", json=payload)
        if res.status_code == 200:
            st.success("✅ Feedback submitted successfully!")
            go_to_step(4)  # Move to thank you page after successful submission
            return True
        else:
            st.error(f"Failed to submit: {res.text}")
            return False
    except Exception as e:
        st.error(f"Error while submitting: {e}")
        return False

# Step 1: Select Evaluation
if st.session_state.step == 1:
    st.title("🧪 Select Evaluation")
    try:
        res = requests.get(f"{API_BASE_URL}/evaluations?active=true")
        res.raise_for_status()
        evaluations = res.json()
    except Exception as e:
        st.error(f"Failed to fetch evaluations: {e}")
        st.stop()

    eval_titles = {e['Title']: e['ID'] for e in evaluations}
    selected_title = st.selectbox("Choose an Evaluation", list(eval_titles.keys()))
    selected_eval_id = eval_titles[selected_title]
    selected_meta = next((e for e in evaluations if e['ID'] == selected_eval_id), None)
    description = selected_meta.get("Description", "")
    prompt_text = extract_prompt_from_description(description)
    st.session_state.prompt_text = prompt_text

    if selected_meta:
        try:
            json_resp = requests.get(f"{API_BASE_URL}/evaluation/{selected_meta['ID']}")
            eval_data = json_resp.json()
            if isinstance(eval_data, dict):
                eval_data = [eval_data]
            model_count = len(eval_data)
            st.markdown(f"**Models in this evaluation:** {model_count}")
            st.markdown(f"**Description:** {selected_meta.get('Description', '')}")
        except Exception as e:
            st.error(f"Failed to fetch model count: {e}")

    if st.button("Next ▶️"):
        st.session_state.selected_eval = selected_eval_id
        try:
            json_resp = requests.get(f"{API_BASE_URL}/evaluation/{selected_eval_id}")
            eval_data = json_resp.json()
            if isinstance(eval_data, dict):
                eval_data = [eval_data]
            st.session_state.evaluation_data = eval_data
            st.session_state.step = 2
            st.rerun()  # Force a rerun to update the UI
        except Exception as e:
            st.error(f"Failed to load evaluation data: {e}")

# Step 2: Participant Info
elif st.session_state.step == 2:
    st.title("👤 Participant Info")
    st.selectbox("How many models to show per page?", [5, 10, 20, 50, 100, "All"], key="models_per_page_select")
    if st.session_state.models_per_page_select == "All":
        st.session_state.models_per_page = len(st.session_state.evaluation_data)
    else:
        st.session_state.models_per_page = int(st.session_state.models_per_page_select)

    with st.form("user_info_form"):
        age_group = st.selectbox("Age", ["18–25", "26–35", "36–45", "46–60", "60+"])
        gender = st.selectbox("Gender", ["Male", "Female", "Other", "Prefer not to say"])
        dsl_experience = st.radio("Experience with DSLs", list(LIKERT_OPTIONS2.keys()))
        llm_usage = st.radio("LLM Usage Frequency", list(LIKERT_OPTIONS3.keys()))
        model_names = list({m['model_name'] for m in st.session_state.evaluation_data})
        known_llms = st.multiselect("Which of these LLMs have you heard of?", model_names)
        if st.form_submit_button("Start Evaluation ▶️"):
            st.session_state.feedback_draft = {
                "reviewer_info": {
                    "reviewer_id": st.session_state.reviewer_id,
                    "age": age_group,
                    "gender": gender,
                    "dsl_experience": dsl_experience,
                    "llm_usage": llm_usage,
                    "known_llms": known_llms,
                    "timestamp": str(datetime.now())
                },
                "evaluation_id": st.session_state.selected_eval,
                "responses": []
            }
            save_draft()
            st.session_state.step = 3
            st.rerun()  # Force a rerun to update the UI

# Step 3: Evaluate LLM Outputs
elif st.session_state.step == 3:
    st.title("📊 Evaluate LLM Outputs")
    MODELS_PER_PAGE = st.session_state.models_per_page
    start = st.session_state.page * MODELS_PER_PAGE
    end = start + MODELS_PER_PAGE
    total = len(st.session_state.evaluation_data)
    current_batch = st.session_state.evaluation_data[start:end]

    st.progress(len(st.session_state.completed_models) / total)
    st.write(f"Evaluated {len(st.session_state.completed_models)} of {total}")

    # Clear previous responses for the current batch to avoid duplicates
    for i, entry in enumerate(current_batch):
        index = start + i
        # Remove any existing responses for this model if present
        st.session_state.feedback_draft["responses"] = [
            r for r in st.session_state.feedback_draft.get("responses", [])
            if r.get("model_name") != entry["model_name"] or r.get("parameters") != entry["parameters"]
        ]

    for i, entry in enumerate(current_batch):
        index = start + i
        st.markdown("---")
        # st.subheader(f"{entry['model_name']} ({entry['parameters']})")
        st.subheader(f"{entry['model_name']} ({entry['parameters']})", help=st.session_state.get("prompt_text", ""))

        with st.expander("🔍 View DSL Output"):
            st.code(entry['output'], language="dsl")
        concepts = extract_concepts(entry['output'])
        if concepts:
            st.markdown("**🧠 Extracted Concepts:** " + ", ".join(concepts))

        cols = st.columns(4)
        ratings = {}
        questions = [
            ("Semantic Correctness", "semantic"),
            ("Concept Identification Quality", "concept"),
            ("Completeness of Model", "complete"),
            ("Use of Advanced Features", "advanced")
        ]

        for col, (label, key) in zip(cols, questions):
            with col:
                selected = st.selectbox(label, ["Select..."] + list(LIKERT_OPTIONS.keys()), key=f"{key}_{index}")
                ratings[key] = LIKERT_OPTIONS.get(selected)

        show_general_comment = st.checkbox("➕ Add General Comment", key=f"gen_comment_toggle_{index}")
        general_comment = ""
        if show_general_comment:
            general_comment = st.text_area("📝 General Comments", key=f"gen_{index}")

        response = {
            "model_name": entry["model_name"],
            "parameters": entry["parameters"],
            **ratings,
            "general_comment": general_comment
        }

        st.session_state.feedback_draft["responses"].append(response)
        if all(ratings.values()):
            st.session_state.completed_models.add(index)
        
    # Save draft outside the loop to avoid excessive disk writes
    save_draft()

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.session_state.page > 0 and st.button("⬅️ Previous"):
            st.session_state.page -= 1
            st.rerun()  # Force a rerun to update the UI
    with col2:
        if end < total and st.button("Next ➡️"):
            st.session_state.page += 1
            st.rerun()  # Force a rerun to update the UI
    with col3:
        if st.button("📤 Submit Feedback Now"):
            if submit_feedback():
                # The successful submission will already trigger a rerun to step 4
                pass

# Step 4: Thank you screen
elif st.session_state.step == 4:
    st.title("🎉 Thank You!")
    st.success("Your feedback has been successfully submitted. Thank you for your participation!")
    
    if st.button("🏠 Return to Home", key="return_home"):
        # Reset all states
        st.session_state.step = 1
        st.session_state.selected_eval = None
        st.session_state.evaluation_data = []
        st.session_state.feedback_draft = {}
        st.session_state.page = 0
        st.session_state.completed_models = set()
        st.session_state.reviewer_id = str(uuid.uuid4())
        st.rerun()  # Force a rerun to update the UI