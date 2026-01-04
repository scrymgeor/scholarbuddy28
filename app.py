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
# 4. UI
# ==========================================
if user_input := st.chat_input("How are you feeling?"):
    with st.chat_message("user"):
        st.write(user_input)

    try:
        prompt = f"""
        Analyze mood: "{user_input}".
        Return JSON: {{ "action": "CLEAR" or "ADD", "topic": "Study Topic", "reply": "Short advice" }}
        """
        response = model.generate_content(prompt)
        text = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(text)
        
        reply = data.get('reply')
        action = data.get('action')

        if action == "ADD":
            add_task_to_db(f"Deep Work: {data.get('topic')}")
        elif action == "CLEAR":
            reduce_load_db()

        with st.chat_message("assistant"):
            st.write(reply)
            
    except Exception as e:
        st.error(f"AI Error: {e}")











