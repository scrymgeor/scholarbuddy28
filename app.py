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
st.title("🌊 Echo")

# 🔑 SECURE LOGIN
# This looks for the key in the "Vault" (Streamlit Secrets)
# It will NOT look in this file.
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("🚨 API Key is missing! Please add it to Streamlit Secrets.")
    st.stop()
model = genai.GenerativeModel('gemini-2.5-pro')
# Page Config - Rebranded to "Echo"
st.set_page_config(page_title="Echo", page_icon="🌊", layout="wide")

# Connect to Firebase (Safe Connection)
# We check if it's already connected so it doesn't crash on reload
if not firebase_admin._apps:
    try:
        # Make sure firebase_key.json is in your folder!
        cred = credentials.Certificate("firebase_key.json") 
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"❌ Failed to connect to Firebase: {e}")
        st.warning("Did you download your key and rename it to 'firebase_key.json'?")

# Get Database Client
try:
    db = firestore.client()
except:
    db = None

# ==========================================
# 2. FIREBASE FUNCTIONS (The "Echo" Logic)
# ==========================================
def get_echo_tasks():
    """Fetch tasks from the 'echo_schedule' collection."""
    if db is None: return []
    # Get tasks ordered by time
    docs = db.collection('echo_schedule').order_by('created_at', direction=firestore.Query.DESCENDING).stream()
    tasks = []
    for doc in docs:
        tasks.append(doc.to_dict())
    return tasks

def add_task_to_db(activity):
    """Add a new activity to the schedule."""
    if db is None: return
    new_task = {
        "summary": activity,
        "type": "Study",
        "created_at": datetime.now().isoformat()
    }
    db.collection('echo_schedule').add(new_task)

def reduce_load_db():
    """Remove the most recent task to lighten the load."""
    if db is None: return None
    
    try:
        # Check if collection exists and has data
        docs = db.collection('echo_schedule').order_by('created_at', direction=firestore.Query.DESCENDING).limit(1).stream()
        
        deleted_item = None
        found_any = False

        for doc in docs:
            found_any = True
            data = doc.to_dict()
            deleted_item = data.get('summary', 'Task')
            doc.reference.delete() # Delete from Firebase
            
        if not found_any:
            return None # List was empty, nothing to delete
            
        return deleted_item

    except Exception as e:
        # If the database is missing or connection fails, just print to console, don't crash app
        print(f"Database Error during delete: {e}")
        return None

# ==========================================
# 3. THE UI (Streamlit)
# ==========================================
# Header Section
st.title("🌊 Echo")
st.markdown("### Your schedule echoes your state of mind.")
st.markdown("---")

col1, col2 = st.columns([2, 1])

# --- LEFT COLUMN: The Conversation ---
with col1:
    st.subheader("💭 The Vibe Check")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
        # Initial greeting
        if len(st.session_state.messages) == 0:
            st.session_state.messages.append({"role": "assistant", "content": "I am Echo. How is your energy flowing right now?"})

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # User Input
    if user_input := st.chat_input("Ex: 'I am overwhelmed' or 'I feel powerful'"):
        # 1. Show User Message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # 2. GEMINI BRAIN LOGIC
        try:
            with st.spinner("Echo is listening..."):
                # System Prompt tells Gemini how to behave
                prompt = f"""
                You are "Echo", an empathetic schedule manager. 
                Analyze the user's input: "{user_input}"
                
                1. If the user is STRESSED/TIRED: Return action "CLEAR" and a calming reply.
                2. If the user is MOTIVATED/ENERGETIC: Return action "ADD" and an encouraging reply.
                3. If neutral/unsure: Return action "NONE".
                
                Return ONLY this JSON format:
                {{ "action": "CLEAR" or "ADD" or "NONE", "topic": "Name of study topic (if adding)", "reply": "Your message here" }}
                """
                
                response = model.generate_content(prompt)
                
                # Parse JSON (Clean up code blocks if Gemini adds them)
                text = response.text.replace('```json', '').replace('```', '').strip()
                data = json.loads(text)
                
                action = data.get('action')
                bot_reply = data.get('reply')
                topic = data.get('topic', 'Focus Session')

                # 3. UPDATE FIREBASE (REAL-TIME)
                if action == "ADD":
                    add_task_to_db(f"Deep Work: {topic}")
                    st.toast("🌊 Echo added a session to your flow.", icon="➕")
                    
                elif action == "CLEAR":
                    removed = reduce_load_db()
                    if removed:
                        st.toast(f"🌊 Echo removed '{removed}' to give you space.", icon="💨")
                    else:
                        bot_reply += " (Your schedule is already clear, take a breath)."

                # 4. Show Assistant Response
                st.session_state.messages.append({"role": "assistant", "content": bot_reply})
                with st.chat_message("assistant"):
                    st.markdown(bot_reply)
                
        except Exception as e:
            st.error(f"Echo got confused: {e}")

# --- RIGHT COLUMN: The Database View ---
with col2:
    st.subheader("📅 Your Flow")
    
    # Manual Refresh Button (Streamlit doesn't auto-refresh from DB without interaction)
    if st.button("🔄 Sync Echo"):
        st.rerun()

    # Get Data from Firebase
    tasks = get_echo_tasks()
    
    if not tasks:
        st.info("Your schedule is clear like water.")
        st.markdown("Typing *'I am motivated'* to start.")
    else:
        st.markdown("**Upcoming Sessions:**")
        for task in tasks:
            # Card UI for tasks
            st.success(f"**{task['summary']}**")







