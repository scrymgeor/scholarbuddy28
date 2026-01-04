import streamlit as st
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
import json
from datetime import datetime

# ==========================================
# 1. SETUP
# ==========================================
# 🔑 PASTE KEY HERE
GOOGLE_API_KEY = "PASTE_YOUR_GEMINI_KEY_HERE"

genai.configure(api_key=GOOGLE_API_KEY)

st.set_page_config(page_title="Echo", page_icon="🌊", layout="wide")
st.title("🌊 Echo (Debug Mode)")

# ==========================================
# 🛑 DEBUG SECTION (Find the working model)
# ==========================================
st.warning("🔍 Checking available models...")
try:
    available_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            available_models.append(m.name)
    
    st.success(f"✅ Google says you can use these models: {available_models}")
    
    # AUTOMATICALLY PICK A WORKING MODEL
    if 'models/gemini-1.5-flash' in available_models:
        model_name = 'gemini-1.5-flash'
    elif 'models/gemini-pro' in available_models:
        model_name = 'gemini-pro'
    else:
        # Pick the first one available
        model_name = available_models[0].replace('models/', '')

    st.info(f"🚀 Switching to model: **{model_name}**")
    model = genai.GenerativeModel(model_name)

except Exception as e:
    st.error(f"❌ API Key Error: {e}")
    st.stop()

# ==========================================
# 2. FIREBASE CONNECTION
# ==========================================
if not firebase_admin._apps:
    try:
        # Load key from Streamlit Secrets or File
        if "firebase" in st.secrets:
            # Create a dictionary from secrets
            key_dict = dict(st.secrets["firebase"])
            cred = credentials.Certificate(key_dict)
        else:
            cred = credentials.Certificate("firebase_key.json") 
            
        firebase_admin.initialize_app(cred)
    except Exception as e:
        # Don't show error if it's just a file missing in cloud, we handle it
        pass

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




