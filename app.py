import streamlit as st
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from datetime import datetime

# ==========================================
# 1. SETUP
# ==========================================
st.set_page_config(page_title="Echo", page_icon="🌊", layout="wide")

# 🔑 SECURE GEMINI LOGIN
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("🚨 Gemini API Key is missing in Secrets!")
    st.stop()

# ==========================================
# 2. FIREBASE CONNECTION (With Auto-Repair)
# ==========================================
if not firebase_admin._apps:
    try:
        # Load the raw file
        with open("firebase_key.json") as f:
            key_dict = json.load(f)

        # 🔧 FIX: Repair the Private Key string
        # This fixes the "Windows vs Linux" newline error
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")

        # Connect
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
        
    except FileNotFoundError:
        st.error("❌ firebase_key.json not found on server!")
        st.stop()
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        st.stop()

# Get DB Client
try:
    db = firestore.client()
except:
    db = None

# ==========================================
# 3. ECHO LOGIC
# ==========================================
def get_echo_tasks():
    if db is None: return []
    try:
        docs = db.collection('echo_schedule').order_by('created_at', direction=firestore.Query.DESCENDING).stream()
        return [doc.to_dict() for doc in docs]
    except:
        return []

def add_task_to_db(activity):
    if db is None: return
    db.collection('echo_schedule').add({
        "summary": activity,
        "created_at": datetime.now().isoformat()
    })

def reduce_load_db():
    if db is None: return None
    try:
        docs = db.collection('echo_schedule').order_by('created_at', direction=firestore.Query.DESCENDING).limit(1).stream()
        for doc in docs:
            data = doc.to_dict()
            doc.reference.delete()
            return data.get('summary', 'Task')
    except:
        return None

# ==========================================
# 4. THE UI (Split Columns)
# ==========================================
st.title("🌊 Echo")
st.markdown("### Your schedule echoes your state of mind.")

col1, col2 = st.columns([2, 1])

# --- LEFT COLUMN: Chat ---
with col1:
    st.subheader("💭 The Vibe Check")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_input := st.chat_input("Ex: 'I am overwhelmed' or 'I feel powerful'"):
        # Show User Message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Gemini Logic
        try:
            prompt = f"""
            Analyze mood: "{user_input}".
            Return JSON: {{ "action": "CLEAR" or "ADD", "topic": "Study Topic", "reply": "Short advice" }}
            """
            response = model.generate_content(prompt)
            text = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(text)
            
            action = data.get('action')
            bot_reply = data.get('reply')

            # Update DB
            if action == "ADD":
                add_task_to_db(f"Deep Work: {data.get('topic')}")
                st.toast("Added session!", icon="➕")
            elif action == "CLEAR":
                removed = reduce_load_db()
                if removed: st.toast(f"Removed: {removed}", icon="💨")

            # Show and Save Assistant Response
            st.session_state.messages.append({"role": "assistant", "content": bot_reply})
            with st.chat_message("assistant"):
                st.markdown(bot_reply)
            
            # Rerun to update the calendar on the right
            st.rerun()
                
        except Exception as e:
            st.error(f"Echo is thinking... (Error: {e})")

# --- RIGHT COLUMN: Calendar ---
with col2:
    st.subheader("📅 Your Flow")
    if st.button("🔄 Sync Echo"):
        st.rerun()

    tasks = get_echo_tasks()
    
    if not tasks:
        st.info("Your schedule is clear.")
    else:
        for task in tasks:
            st.success(f"**{task.get('summary', 'Task')}**")













