import streamlit as st
import google.generativeai as genai
import json
from datetime import datetime

# ==========================================
# 1. SETUP & STYLING
# ==========================================
st.set_page_config(page_title="Echo", page_icon="🌊", layout="wide")

# OCEAN THEME CSS
st.markdown("""
<style>
    .stApp { background: linear-gradient(to bottom right, #0f2027, #203a43, #2c5364); color: white; }
    .stChatMessage { background-color: rgba(255, 255, 255, 0.05); border-radius: 15px; border: 1px solid rgba(255, 255, 255, 0.1); }
    div[data-testid="stAlert"] { background: rgba(255, 255, 255, 0.1); border-radius: 12px; color: white; border: 1px solid rgba(255,255,255,0.2); }
    .stTextInput input { background-color: rgba(0, 0, 0, 0.3); color: white; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.2); }
    .stButton button { background: linear-gradient(45deg, #00c6ff, #0072ff); color: white; border-radius: 20px; border: none; }
</style>
""", unsafe_allow_html=True)

# 🔑 SECURE GEMINI LOGIN
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    st.error("🚨 Gemini API Key is missing in Secrets!")
    st.stop()

# ==========================================
# 2. LOGIC (Calendar + Backlog)
# ==========================================

# A. The Calendar (Time Slots)
if "echo_calendar" not in st.session_state:
    st.session_state.echo_calendar = [
        {"time": "09:00 AM", "task": "Morning Routine", "locked": True},
        {"time": "11:00 AM", "task": None, "locked": False},
        {"time": "01:00 PM", "task": None, "locked": False},
        {"time": "03:00 PM", "task": None, "locked": False},
        {"time": "05:00 PM", "task": None, "locked": False},
    ]

# B. The Backlog (Tasks waiting for assignment)
if "echo_backlog" not in st.session_state:
    st.session_state.echo_backlog = [
        "Math: Calculus Ch.4",
        "Physics: Lab Report",
        "History: Essay Draft"
    ]

def schedule_next_task():
    """Moves top task from Backlog -> First Empty Slot"""
    if not st.session_state.echo_backlog:
        return None, "Backlog is empty!"
    
    task_name = st.session_state.echo_backlog[0]

    for slot in st.session_state.echo_calendar:
        if slot["task"] is None:
            slot["task"] = task_name
            st.session_state.echo_backlog.pop(0)
            return task_name, slot["time"]
            
    return None, "No time slots left!"

def clear_upcoming_schedule():
    """Moves tasks from Calendar -> Backlog"""
    cleared_count = 0
    for slot in st.session_state.echo_calendar:
        if not slot["locked"] and slot["task"] is not None:
            # Return to backlog
            st.session_state.echo_backlog.insert(0, slot["task"])
            slot["task"] = None
            cleared_count += 1
    return cleared_count

# ==========================================
# 3. THE UI
# ==========================================
st.title("Chat With Echo")
st.markdown("### The calendar that breathes with you.")

col1, col2 = st.columns([2, 1])

# --- LEFT COLUMN: Chat ---
with col1:
    st.subheader("💭 The Vibe Check")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.messages.append({"role": "assistant", "content": "I see your task list. How is your energy?"})

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_input := st.chat_input("Ex: 'I am motivated' or 'I am stressed'"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        try:
            # AI LOGIC
            prompt = f"""
            User says: "{user_input}"
            1. If MOTIVATED: Return JSON {{ "action": "FILL", "reply": "Great! Filling your empty slots." }}
            2. If STRESSED: Return JSON {{ "action": "CLEAR", "reply": "Understood. Clearing the afternoon so you can rest." }}
            3. Otherwise: {{ "action": "NONE", "reply": "Tell me more." }}
            """
            response = model.generate_content(prompt)
            text = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(text)
            
            action = data.get('action')
            bot_reply = data.get('reply')

            if action == "FILL":
                task, time = schedule_next_task()
                if task:
                    st.toast(f"Scheduled '{task}' for {time}", icon="📅")
                else:
                    bot_reply += " (Calendar full or Backlog empty!)"
            elif action == "CLEAR":
                count = clear_upcoming_schedule()
                if count > 0:
                    st.toast(f"Cleared {count} slots.", icon="💨")

            st.session_state.messages.append({"role": "assistant", "content": bot_reply})
            with st.chat_message("assistant"):
                st.markdown(bot_reply)
            
            st.rerun()
                
        except Exception as e:
            st.error(f"Error: {e}")

# --- RIGHT COLUMN: Calendar + Inputs ---
with col2:
    st.subheader("📅 Today's Timeline")
    
    # 1. THE CALENDAR VISUAL
    for slot in st.session_state.echo_calendar:
        time = slot["time"]
        task = slot["task"]
        
        if task:
            # Filled Slot (Blue Glass)
            st.info(f"**{time}** | {task}")
        else:
            # Empty Slot (Ghost)
            st.markdown(f"""
            <div style="padding:10px; border-radius:10px; margin-bottom:10px; background:rgba(255,255,255,0.05); color: #aaa; border: 1px dashed #555;">
                {time} | <i>Free Slot</i>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    
    # 2. MANUAL TASK ENTRY (The Feature You Requested)
    st.subheader("📝 Backlog")
    
    # Add Task Form
    with st.form("add_task", clear_on_submit=True):
        new_task = st.text_input("Add a task to backlog:", placeholder="E.g. Chemistry Test Prep")
        if st.form_submit_button("➕ Add Task"):
            if new_task:
                st.session_state.echo_backlog.append(new_task)
                st.rerun()

    # List of Tasks (with Delete)
    if st.session_state.echo_backlog:
        for i, item in enumerate(st.session_state.echo_backlog):
            c1, c2 = st.columns([5, 1])
            c1.code(item) # Shows task in grey box
            if c2.button("❌", key=f"del_{i}"):
                st.session_state.echo_backlog.pop(i)
                st.rerun()
    else:
        st.caption("Backlog is empty!")







