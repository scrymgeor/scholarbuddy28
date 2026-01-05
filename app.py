import streamlit as st
import google.generativeai as genai
import json
import random
from datetime import datetime

# ==========================================
# 1. SETUP
# ==========================================
st.set_page_config(page_title="Echo", page_icon="🌊", layout="wide")

# 🔑 SECURE GEMINI LOGIN
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    # Using the standard model that always works
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    st.error("🚨 Gemini API Key is missing in Secrets!")
    st.stop()

# ==========================================
# 2. SIMULATED DATABASE (The "Magic" Trick)
# ==========================================
# Instead of Firebase, we use Session State.
# It behaves EXACTLY like a database for the demo.
if "echo_db" not in st.session_state:
    st.session_state.echo_db = [
        {"summary": "Finish Hackathon Project", "created_at": "2023-10-27T10:00:00"},
        {"summary": "Review Physics Notes", "created_at": "2023-10-27T12:00:00"}
    ]

def get_echo_tasks():
    # Return the fake list reversed (newest first)
    return st.session_state.echo_db[::-1]

def add_task_to_db(activity):
    st.session_state.echo_db.append({
        "summary": activity,
        "created_at": datetime.now().isoformat()
    })

def reduce_load_db():
    if len(st.session_state.echo_db) > 0:
        # Remove the last item (most recent)
        removed = st.session_state.echo_db.pop()
        return removed['summary']
    return None

# ==========================================
# 3. THE UI
# ==========================================
st.title("🌊 Echo")
st.markdown("### Your schedule echoes your state of mind.")

col1, col2 = st.columns([2, 1])

# --- LEFT COLUMN: Chat ---
with col1:
    st.subheader("💭 The Vibe Check")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.messages.append({"role": "assistant", "content": "I am Echo. How is your energy flowing right now?"})

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_input := st.chat_input("Ex: 'I am overwhelmed' or 'I feel powerful'"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        try:
            # AI LOGIC
            prompt = f"""
            Analyze mood: "{user_input}".
            Return JSON: {{ "action": "CLEAR" or "ADD", "topic": "Study Topic", "reply": "Short empathetic advice" }}
            """
            response = model.generate_content(prompt)
            text = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(text)
            
            action = data.get('action')
            bot_reply = data.get('reply')

            # UPDATE "DATABASE"
            if action == "ADD":
                add_task_to_db(f"Deep Work: {data.get('topic', 'Focus')}")
                st.toast("Added session!", icon="➕")
            elif action == "CLEAR":
                removed = reduce_load_db()
                if removed: st.toast(f"Removed: {removed}", icon="💨")

            st.session_state.messages.append({"role": "assistant", "content": bot_reply})
            with st.chat_message("assistant"):
                st.markdown(bot_reply)
            
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
        st.info("Your schedule is clear like water.")
    else:
        for task in tasks:
            st.success(f"**{task.get('summary', 'Task')}**")
