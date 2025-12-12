import streamlit as st
import re # Essential for image tag parsing
from google import genai
from google.genai import types
from streamlit_mic_recorder import speech_to_text # External component for voice input

# --- CUSTOM UI STYLING FUNCTION (LIGHT THEME WITH GREEN TEXT) ---

def set_custom_ui_style():
    """Injects custom CSS for a LIGHT theme with green primary text."""
    st.markdown("""
    <style>
    /* 1. Main Background: Light Theme (White/Faint Gray) */
    .stApp {
        background-color: #f0f2f6; /* Light gray/default background */
        color: #00ff00; /* Primary text color set to BRIGHT GREEN */
    }

    /* 2. Sidebar Color */
    .css-1d391kg, .css-1y4p8a {
        background-color: #ffffff; /* White sidebar */
        color: #008000; /* Darker green text for contrast */
    }
    
    /* 3. Headers and Titles (Kept Clinical Blue for visual structure/branding) */
    h1, h2, h3, h4 {
        color: #00a8cc; /* Clinical Cyan Blue for emphasis */
    }

    /* 4. Chat Messages (Assistant: Light background, User: Default/Light contrast) */
    .stChatMessage [data-testid="stChatMessageContent"] {
        background-color: #e0eaff; /* Very faint blue for assistant bubble */
        border-left: 5px solid #00a8cc; /* Clinical cyan border */
        padding: 15px;
        border-radius: 8px;
        box-shadow: 1px 1px 5px rgba(0, 0, 0, 0.1);
        color: #008000; /* Darker green text for readability on light background */
    }
    
    /* Ensure user messages are readable against the light background */
    .stChatMessage {
        color: #008000; /* Darker green for readability */
    }
    
    /* Ensure input text fields are readable (must be dark text on light background) */
    [data-testid="textInput"] input, 
    [data-testid="stTextarea"] textarea, 
    [data-testid="stForm"] {
        color: #1e1e1e; /* Dark text for input fields */
        background-color: #ffffff;
    }

    /* 5. Primary Button (Clinical blue remains for action) */
    [data-testid="baseButton-primary"] {
        background-color: #00a8cc;
        border-color: #00a8cc;
        color: white !important;
    }
    [data-testid="baseButton-primary"]:hover {
        background-color: #007c99;
        border-color: #007c99;
    }

    /* 6. Info Boxes (Need bright contrast) */
    [data-testid="stAlert"] {
        background-color: #d1ecf1; /* Light cyan background for info */
        color: #0c5460; /* Dark text for alerts */
    }
    </style>
    """, unsafe_allow_html=True)

# --- CALL THE STYLING FUNCTION FIRST ---
set_custom_ui_style()

# --- 1. CONFIGURATION AND SAFETY ---

# UPDATED SYSTEM INSTRUCTION: Enforces brevity, structure, and image tagging
SYSTEM_INSTRUCTION = """
You are a helpful, strictly non-diagnostic Healthcare Companion AI.

CRITICAL OUTPUT RULES:
1. **BE CONCISE:** Do not write long paragraphs. Keep responses short and easy to read.
2. **STRUCTURE:** Your response must follow this exact format:
    - **⚠️ Disclaimer:** "General Info Only. Consult a Doctor."
    - **📝 Summary:** A 1-2 sentence explanation of the problem/symptom.
    - **💡 Solutions & Tips:** A bulleted list of 3-5 actionable general tips or home remedies (tailored to Ayurvedic or General/Modern Wellness based on user request).
3. **VISUALS:** Assess if the user would understand better with a diagram. If yes, insert a tag like 


[Image of human digestive system]

 or 


[Image of knee anatomy]

 at the end of the summary. Do not use images for abstract concepts like "hard work" or generic people. Only use if it adds instructive value.
4. **LANGUAGE:** Output in the requested language.
"""

MODEL_NAME = 'gemini-2.5-flash'
APP_TITLE = "🩺 HealthCare Companion (Dr.Drug Lord)"

# --- CONFIGURATION CONSTANTS ---
TRIGGER_KEYWORDS = ["symptom", "constipation", "pain", "fever", "headache", "cold", "flu", "cough", "heart", "stomach", "skin"]
AGE_RANGES = ["0-12", "13-17", "18-45", "46-65", "65+"]
GENDER_OPTIONS = ["Male", "Female", "Prefer Not to Say"]
THERAPY_OPTIONS = ["Ayurvedic Suggestion", "General/Modern Wellness"] 

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
    """Initializes, stores, and returns the persistent Gemini Client."""
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
    """Resets the chat session state."""
    client = get_gemini_client() 
    if not client:
        return

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION
    )
    
    st.session_state['gemini_chat'] = client.chats.create(model=MODEL_NAME, config=config)
    
    st.session_state.messages = [{"role": "assistant", "content": 
        "Welcome!⛑ I am your Dr Drug Lord. Ask me about your symptoms."}]
    st.session_state.asking_for_details = False 
    st.session_state.user_details = {} 
    st.session_state.show_prescription_form = False
    st.session_state.user_choice_therapy = THERAPY_OPTIONS[1] 
    
    st.rerun() 

# --- IMAGE PARSING AND DISPLAY FUNCTION ---

def parse_and_display_response(full_response, container):
    """
    Parses the full response for the 

[Image of X]
 tag.
    Displays the text content, and replaces the tag with an image holder.
    """
    # 1. Regular expression to find all 

[Image of X]
 tags
    image_tags = re.findall(r'\', full_response)
    
    # 2. Clean the text response by removing the image tags
    clean_text = re.sub(r'\', '', full_response).strip()
    
    # 3. Display the text in the container
    container.markdown(clean_text)
    
    # 4. Display Image Placeholder/Request
    if image_tags:
        container.markdown("---")
        container.subheader("🖼️ Visual Aid Suggested")
        
        for prompt in image_tags:
            # THIS IS THE IMAGE PLACEHOLDER FOR DEMONSTRATION
            container.markdown(
                f"""
                <div style="border: 2px dashed #00a8cc; padding: 10px; border-radius: 5px; background-color: #f0f8ff; margin-top: 10px;">
                    <p style="color: #008000; margin: 0;"><b>Image Request:</b> {prompt}</p>
                    <p style="color: #6a0000; font-size: 0.9em; margin: 0;">
                        (This feature successfully extracts the image prompt for a separate image API service.)
                    </p>
                </div>
                """, unsafe_allow_html=True
            )

# --- HELPER FUNCTION FOR AI RESPONSE (TEXT ONLY) ---

def handle_final_response(base_prompt, is_medicine_request=False):
    """
    Handles the API call and streams the text response.
    Parses the final response for image tags.
    """
    client = get_gemini_client()
    if not client:
        return

    target_lang = st.session_state.current_language
    
    if is_medicine_request:
        final_prompt = f"{base_prompt}\n\nOutput in *{target_lang}*. Keep it brief: Usage + Key Symptoms treated."
    else:
        final_prompt = (
            f"{base_prompt}\n\n"
            f"Constraint: Respond in {target_lang}. "
            f"Keep it concise. Structure as: 1. Short Summary (assess if [Image of...] tag is needed and insert it IMMEDIATELY after the summary). 2. Bullet points for Solutions."
        )

    display_content = base_prompt if not is_medicine_request else f"Requesting info for medicine: {base_prompt}"
    st.session_state.messages.append({"role": "user", "content": display_content})
    
    full_response = ""
    
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        try:
            message_placeholder.markdown("Thinking... 🧠")
            
            response_stream = st.session_state['gemini_chat'].send_message_stream(final_prompt) 
            
            full_stream_response = ""
            temp_streaming_placeholder = st.empty() 
            for chunk in response_stream:
                full_stream_response += chunk.text
                temp_streaming_placeholder.markdown(full_stream_response + "▌") 

            temp_streaming_placeholder.empty()

            parse_and_display_response(full_stream_response, message_placeholder)
            full_response = full_stream_response
            
        except Exception as e:
            full_response = f"An error occurred: {e}"
            message_placeholder.markdown(full_response)

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

    original_symptom = next(
        (msg['content'] for msg in reversed(st.session_state.messages) 
         if msg['role'] == 'user' and not msg['content'].startswith('Requesting info')),
        "General health enquiry."
    )
    
    prompt = (
        f"User Complaint: {original_symptom}\n"
        f"Context: {user_gender}, Age {user_age}, Weight {user_weight}kg\n"
        f"Preferred Approach: {user_therapy_choice}\n\n"
        f"Task: Provide a VERY SHORT, structured response.\n"
        f"1. Explain the problem in 1-2 sentences. Crucially, assess if an anatomical or procedural diagram helps explain the condition (e.g., knee anatomy for knee pain, digestive system for constipation). If a diagram helps, insert the appropriate  tag immediately after the summary sentence.\n"
        f"2. Provide 4-5 bullet points of clear solutions/remedies based on '{user_therapy_choice}'.\n"
        f"Do not lecture. Go straight to the point."
    )

    handle_final_response(prompt)
    st.rerun()

# --- 3. STREAMLIT APP UI ---

st.set_page_config(page_title=APP_TITLE, page_icon="🩺", layout="wide")
st.title(APP_TITLE)

if 'gemini_chat' not in st.session_state:
    reset_chat()
    # No st.rerun() here, as reset_chat already calls it after initialization. 

# --- SIDEBAR CONTROLS ---

with st.sidebar:
    st.header("⚙ Settings")
    
    # 1. LANGUAGE SELECTOR
    st.subheader("Select Reading Language")
    selected_lang_key = st.selectbox(
        "Choose the language for the answer:",
        options=list(LANGUAGE_MAP.keys()),
        index=0
    )
    st.session_state.current_language = LANGUAGE_MAP[selected_lang_key]
    
    st.markdown("---")
    
    # 2. MEDICINE INFO BUTTON
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

# Safety Disclaimer
with st.container(border=True):
    st.markdown(f"""
    <div style="padding: 5px;">
    <h4 style="color: #FF7F7F; margin-top: 0;">⚠ SAFETY FIRST (DISCLAIMER)</h4>
    <p style="color: #008000;">I provide general information only. <b>I am not a doctor.</b> Always consult a professional.</p>
    </div>
    """, unsafe_allow_html=True)

# Display Chat History
for i, message in enumerate(st.session_state.messages):
    is_last_assistant_message = (message["role"] == "assistant" and i == len(st.session_state.messages) - 1)

    with st.chat_message(message["role"]):
        if is_last_assistant_message:
            # Use parser for the latest assistant message to handle image tag display
            parse_and_display_response(message["content"], st.container())
        else:
            # Display all other messages normally
            st.markdown(message["content"])

# --- INTERACTIVE FORMS ---

# 1. MEDICINE INFORMATION FORM
if st.session_state.show_prescription_form:
    with st.form("medicine_info_form"):
        st.subheader(f"💊💉 Medicine Information ({st.session_state.current_language})")
        st.info("Enter the medicine name to understand its general usage and common symptoms treated.")
        
        medicine_name = st.text_input("Enter Medicine Name (e.g., Dolo 650):")
        
        med_submitted = st.form_submit_button("Get Information", type="secondary")

        if med_submitted and medicine_name:
            med_prompt = (
                f"Please explain the general usage, purpose, and common symptoms treated by the medicine: '{medicine_name}'. "
                f"Provide a clear note on when it is typically used."
            )
            handle_final_response(med_prompt, is_medicine_request=True)
            st.session_state.show_prescription_form = False
            st.rerun()

# 2. CONTEXT DETAILS FORM (Includes Gender, Age, Weight, and Therapy Choice)
if st.session_state.asking_for_details:
    with st.form("context_form"):
        st.subheader("📝 Context Required")
        st.info("Please provide details for better, summarized advice.")
        
        # Details Collection (Gender, Age, Weight)
        col_g, col_a, col_w = st.columns(3)
        with col_g:
            gender = st.radio("👤 Gender", GENDER_OPTIONS, horizontal=True) 
        with col_a:
            age = st.selectbox("📅 Age Range", AGE_RANGES)
        with col_w:
            weight = st.number_input("⚖ Weight (kg)", 1, 300, 70, key="context_weight_input")
        
        st.markdown("---")
        
        # Therapy Choice (Ayurvedic vs. General/Modern Wellness)
        st.subheader("🌿 Preferred Approach")
        therapy_choice = st.radio(
            "Select the focus for the general information:",
            THERAPY_OPTIONS,
            horizontal=False, 
            index=1 
        )

        st.markdown("---")
        
        # Submit Button
        if st.form_submit_button("✅ Get Advice", type="primary"):
            handle_context_form_submit(gender, age, weight, therapy_choice)


# --- MAIN INPUT (Voice & Text) ---

if not st.session_state.asking_for_details and not st.session_state.show_prescription_form:
    st.markdown("---")
    
    col1, col2 = st.columns([1, 4])
    
    with col1:
        # VOICE INPUT: Manual stop added back
        voice_text = speech_to_text(
            language='en', 
            start_prompt="🎤 Speak", 
            stop_prompt="🛑 Stop", # Manual stop button re-added
            just_once=True,
            key='voice_input'
        )
    
    with col2:
        text_input = st.chat_input("Ask about symptoms...")

    user_input = voice_text or text_input

    if user_input:
        if any(k in user_input.lower() for k in TRIGGER_KEYWORDS):
            st.session_state.messages.append({"role": "user", "content": user_input})
            st.session_state.asking_for_details = True
            with st.chat_message("assistant"):
                msg = "*Context Required:* Please fill the form above so I can give you a specific solution."
                st.session_state.messages.append({"role": "assistant", "content": msg})
                st.markdown(msg)
            st.rerun()
        else:
            handle_final_response(user_input)
            st.rerun()
