import streamlit as st
from google import genai
from google.genai import types
from streamlit_mic_recorder import speech_to_text
import re 
# --- External import for generating medical diagrams (Hackathon Feature) ---
import urllib.parse

# --- CUSTOM UI STYLING FUNCTION (DARK THEME WITH GREEN TEXT) ---

def set_custom_ui_style():
    """Injects custom CSS for a dark, professional/clinical appearance with green text."""
    st.markdown("""
    <style>
    /* 1. Main Background: Deep dark theme */
    .stApp {
        background-color: #1e1e1e; /* Deep Charcoal */
        color: #00ff00; /* Primary text color set to Bright Green */
    }

    /* 2. Sidebar Color */
    .css-1d391kg, .css-1y4p8a {
        background-color: #2d2d2d; 
        color: #00ff00; 
    }
    
    /* 3. Headers and Titles */
    h1, h2, h3, h4 {
        color: #00a8cc; /* Clinical Cyan Blue for emphasis */
    }

    /* 4. Chat Messages */
    .stChatMessage [data-testid="stChatMessageContent"] {
        background-color: #383838; 
        border-left: 5px solid #00a8cc; 
        padding: 15px;
        border-radius: 8px;
        box-shadow: 2px 2px 8px rgba(0, 0, 0, 0.4);
        color: #00ff00; 
    }
    
    .stChatMessage {
        color: #00ff00; 
    }

    /* 5. Primary Button */
    [data-testid="baseButton-primary"] {
        background-color: #00a8cc;
        border-color: #00a8cc;
        color: white !important;
    }
    [data-testid="baseButton-primary"]:hover {
        background-color: #007c99;
        border-color: #007c99;
    }

    /* 6. Info Boxes */
    [data-testid="stAlert"] {
        background-color: #004d66; 
        color: #00ff00; 
    }
    
    /* Input fields */
    [data-testid="textInput"], [data-testid="stTextarea"], [data-testid="stForm"] {
        background-color: #2d2d2d;
        color: #00ff00; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- CALL THE STYLING FUNCTION FIRST ---
set_custom_ui_style()

# --- 1. CONFIGURATION AND SAFETY ---

# UPDATED SYSTEM INSTRUCTION: Enforces Images for Anatomy
SYSTEM_INSTRUCTION = """
You are a helpful, strictly non-diagnostic Healthcare Companion AI.

CRITICAL OUTPUT RULES:
1. *BE CONCISE:* Do not write long paragraphs. Keep responses short and easy to read.
2. *STRUCTURE:* Your response must follow this exact format:
    - *⚠ Disclaimer:* "General Info Only. Consult a Doctor."
    - *📝 Summary:* A 1-2 sentence explanation.
    - *🖼 Visual Context:* If the user asks about a body part, organ, or specific physical symptom, YOU MUST output a tag like this: [attachment_0](attachment) or [attachment_1](attachment). 
    - *💡 Solutions & Tips:* A bulleted list of 3-5 actionable general tips or home remedies.
3. *LANGUAGE:* Output in the requested language.
"""

MODEL_NAME = 'gemini-2.0-flash-exp'
APP_TITLE = "🩺 HealthCare Companion (Dr.Drug Lord)"

# --- CONFIGURATION CONSTANTS ---
TRIGGER_KEYWORDS = ["symptom", "constipation", "pain", "fever", "headache", "cold", "flu", "cough", "hurt", "ache"]
AGE_RANGES = ["0-12", "13-17", "18-45", "46-65", "65+"]
GENDER_OPTIONS = ["Male", "Female", "Prefer Not to Say"]
THERAPY_OPTIONS = ["Ayurvedic Suggestion", "General/Modern Wellness"] 

# Language Mapping
LANGUAGE_MAP = {
    'English (Default)': 'English',
    'Kannada (ಕನ್ನಡ)': 'Kannada',
    'Hindi (हिन्दी)': 'Hindi',
    'Telugu (తెలుగు)': 'Telugu'
}

# --- STATE MANAGEMENT ---
if 'asking_for_details' not in st.session_state:
    st.session_state.asking_for_details = False 

if 'user_details' not in st.session_state:
    st.session_state.user_details = {} 

if 'current_language' not in st.session_state:
    st.session_state.current_language = 'English' 

if 'show_prescription_form' not in st.session_state:
    st.session_state.show_prescription_form = False
    
if 'user_choice_therapy' not in st.session_state:
    st.session_state.user_choice_therapy = THERAPY_OPTIONS[1]

# --- 2. INITIALIZATION FUNCTIONS ---

def get_gemini_client():
    if 'gemini_client' in st.session_state:
        return st.session_state['gemini_client']

    if "GEMINI_API_KEY" not in st.secrets:
        st.error("❌ API Key not found. Please set your GEMINI_API_KEY in .streamlit/secrets.toml.")
        return None
        
    try:
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        st.session_state['gemini_client'] = client 
        return client
    except Exception as e:
        st.error(f"❌ Error initializing Gemini Client: {e}")
        return None

def reset_chat():
    client = get_gemini_client() 
    if not client:
        return

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION
    )
    
    st.session_state['gemini_chat'] = client.chats.create(model=MODEL_NAME, config=config)
    
    st.session_state.messages = [{"role": "assistant", "content": 
        "Welcome!⛑ I am your Dr Drug Lord . Ask me about your symptoms ."}]
    st.session_state.asking_for_details = False 
    st.session_state.user_details = {} 
    st.session_state.show_prescription_form = False
    
    st.rerun() 

# --- HELPER: EXTRACT AND RENDER IMAGE ---
def extract_and_display_image(text_response):
    """
    Scans the AI response for [attachment_2](attachment). 
    If found, generates a dynamic medical diagram URL and renders it.
    """
    matches = re.findall(r"\", text_response, re.IGNORECASE)
    
    if matches:
        for match in matches:
            query = match.strip()
            # URL-encode the query for safe use in the prompt
            encoded_query = urllib.parse.quote_plus(query)
            
            # Construct a URL for a medical diagram
            image_url = f"https://image.pollinations.ai/prompt/medical%20anatomy%20diagram%20of%20{encoded_query}%20clean%20white%20background%20high%20quality?width=600&height=400&nologo=true"
            
            st.markdown(f"### 🖼 Anatomical Reference: {query.title()}")
            st.image(image_url, caption=f"Visual aid for: {query}", use_container_width=True)

# --- HELPER FUNCTION FOR AI RESPONSE (TEXT ONLY) ---

def handle_final_response(base_prompt, display_content, is_medicine_request=False):
    """
    Handles the API call. Logs ONLY 'display_content' to history 
    while sending the detailed 'base_prompt' to the AI.
    """
    target_lang = st.session_state.current_language
    
    # Construct the final prompt SENT TO GEMINI
    if is_medicine_request:
        final_prompt = f"{base_prompt}\n\nOutput in {target_lang}. Keep it brief: Usage + Key Symptoms treated."
    else:
        # Instruction for summary, solution, and images (This ensures the structured output)
        final_prompt = (
            f"{base_prompt}\n\n"
            f"Constraint: Respond in {target_lang}. "
            f"Keep it concise. Structure as: 1. Short Summary. 2. Include  tag if relevant. 3. Bullet points for Solutions."
        )

    # Append ONLY the user's clean input (display_content) to history
    st.session_state.messages.append({"role": "user", "content": display_content})
    
    full_response = ""
    
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        if 'gemini_chat' in st.session_state:
            try:
                message_placeholder.markdown("Thinking... 🧠")
                
                # Send the detailed final_prompt (the internal prompt) to Gemini
                response_stream = st.session_state['gemini_chat'].send_message_stream(final_prompt) 
                
                full_response = ""
                for chunk in response_stream:
                    full_response += chunk.text
                    message_placeholder.markdown(full_response + "▌") 

                message_placeholder.markdown(full_response)
                
                # Check and display image after text is complete
                extract_and_display_image(full_response)
                
            except Exception as e:
                full_response = f"An error occurred: {e}"
                message_placeholder.markdown(full_response)
        else:
            full_response = "Error: Chat not initialized."
            message_placeholder.markdown(full_response)

    # Log assistant response to history
    st.session_state.messages.append({
        "role": "assistant", 
        "content": full_response
    })

# --- HELPER FOR CONTEXT FORM SUBMISSION ---

def handle_context_form_submit(user_gender, user_age, user_weight, user_therapy_choice):
    st.session_state.user_details['gender'] = user_gender
    st.session_state.user_details['age'] = user_age
    st.session_state.user_details['weight'] = user_weight
    st.session_state.user_details['therapy'] = user_therapy_choice
    st.session_state.asking_for_details = False 

    # Find the original symptom from chat history (This should be the clean prompt now)
    original_symptom = next(
        (msg['content'] for msg in reversed(st.session_state.messages) 
         if msg['role'] == 'user' and not msg['content'].startswith('Requesting info')),
        "General health enquiry."
    )
    
    # --- 1. PROMPT SENT TO GEMINI (Internal, Detailed Context for AI) ---
    prompt_to_gemini = (
        f"User Complaint: {original_symptom}\n"
        f"Context: {user_gender}, Age {user_age}, Weight {user_weight}kg\n"
        f"Preferred Approach: {user_therapy_choice}\n\n"
        f"Task: Provide a VERY SHORT, structured response.\n"
        f"1. Explain the problem in 1-2 sentences. IF it involves a body part, add a tag like  at the end of the summary.\n"
        f"2. Provide 4-5 bullet points of clear solutions/remedies based on '{user_therapy_choice}'.\n"
        f"Do not lecture. Go straight to the point."
    )
    
    # --- 2. TEXT LOGGED IN CHAT HISTORY (Clean Display) ---
    clean_display_text = (
        f"Regarding *'{original_symptom}'*. "
        f"Context: {user_gender}, Age {user_age}, {user_weight}kg. "
        f"Focus: {user_therapy_choice}."
    )

    # Call the updated function with both prompts
    handle_final_response(prompt_to_gemini, clean_display_text)
    st.rerun()

# --- 3. STREAMLIT APP UI ---

st.set_page_config(page_title=APP_TITLE, page_icon="🩺", layout="wide")
st.title(APP_TITLE)

if 'gemini_chat' not in st.session_state:
    reset_chat()
    st.rerun() 

# --- SIDEBAR CONTROLS ---

with st.sidebar:
    st.header("⚙ Settings")
    st.subheader("Select Reading Language")
    selected_lang_key = st.selectbox(
        "Choose the language for the answer:",
        options=list(LANGUAGE_MAP.keys()),
        index=0
    )
    st.session_state.current_language = LANGUAGE_MAP[selected_lang_key]
    
    st.markdown("---")
    
    if st.button("💊💉 Get Medicine Info"):
        st.session_state.show_prescription_form = not st.session_state.show_prescription_form

    st.markdown("---")
    
    st.button("Clear Chat History", on_click=reset_chat, type="primary")
    
    if st.session_state.user_details:
        st.markdown("---")
        st.caption("Context Provided:")
        for k, v in st.session_state.user_details.items():
            st.caption(f"{k.capitalize()}: {v}")


# --- MAIN CHAT AREA ---

with st.container(border=True):
    st.markdown(f"""
    <div style="padding: 5px;">
    <h4 style="color: #FF7F7F; margin-top: 0;">⚠ SAFETY FIRST (DISCLAIMER)</h4>
    <p style="color: #00ff00;">I provide general information only. <b>I am not a doctor.</b> Always consult a professional.</p>
    </div>
    """, unsafe_allow_html=True)

# Display Chat History (With Image Re-rendering Logic)
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # If it's an assistant message, check if we need to show the image again
        if message["role"] == "assistant":
             extract_and_display_image(message["content"])

# --- INTERACTIVE FORMS ---

if st.session_state.show_prescription_form:
    with st.form("medicine_info_form"):
        st.subheader(f"💊💉 Medicine Information ({st.session_state.current_language})")
        st.info("Enter the medicine name to understand its general usage.")
        medicine_name = st.text_input("Enter Medicine Name (e.g., Dolo 650):")
        med_submitted = st.form_submit_button("Get Information", type="secondary")

        if med_submitted and medicine_name:
            med_prompt = (
                f"Please explain the general usage, purpose, and common symptoms treated by the medicine: '{medicine_name}'. "
                f"Provide a clear note on when it is typically used."
            )
            # LOGGING FIX: Send the detailed prompt, but only the medicine name for clean display
            handle_final_response(med_prompt, f"Requesting info for medicine: {medicine_name}", is_medicine_request=True)
            st.session_state.show_prescription_form = False
            st.rerun()

if st.session_state.asking_for_details:
    with st.form("context_form"):
        st.subheader("📝 Context Required")
        st.info("Please provide details for better, summarized advice.")
        
        col_g, col_a, col_w = st.columns(3)
        with col_g:
            gender = st.radio("👤 Gender", GENDER_OPTIONS, horizontal=True) 
        with col_a:
            age = st.selectbox("📅 Age Range", AGE_RANGES)
        with col_w:
            weight = st.number_input("⚖ Weight (kg)", 1, 300, 70, key="context_weight_input")
        
        st.markdown("---")
        
        st.subheader("🌿 Preferred Approach")
        therapy_choice = st.radio(
            "Select the focus for the general information:",
            THERAPY_OPTIONS, 
            horizontal=False, 
            index=1 
        )

        st.markdown("---")
        
        if st.form_submit_button("✅ Get Advice", type="primary"):
            handle_context_form_submit(gender, age, weight, therapy_choice)


# --- MAIN INPUT (Voice & Text) ---

if not st.session_state.asking_for_details and not st.session_state.show_prescription_form:
    st.markdown("---")
    
    col1, col2 = st.columns([1, 4])
    
    with col1:
        voice_text = speech_to_text(
            language='en', 
            start_prompt="🎤 Speak", 
            stop_prompt="🛑 Stop", 
            key='voice_input'
        )
    
    with col2:
        text_input = st.chat_input("Ask about symptoms...")

    user_input = voice_text or text_input

    if user_input:
        if any(k in user_input.lower() for k in TRIGGER_KEYWORDS):
            # Log the clean symptom to history before opening the form
            st.session_state.messages.append({"role": "user", "content": user_input})
            st.session_state.asking_for_details = True
            with st.chat_message("assistant"):
                msg = "Context Required: Please fill the form above so I can give you a specific solution."
                st.session_state.messages.append({"role": "assistant", "content": msg})
                st.markdown(msg)
            st.rerun()
        else:
            # For general questions, the prompt and display content are the same (user_input)
            handle_final_response(user_input, user_input)
            st.rerun()
