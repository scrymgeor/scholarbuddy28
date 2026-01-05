import streamlit as st
import google.generativeai as genai
import json
from datetime import datetime

# ==========================================
# 1. SETUP
# ==========================================
st.set_page_config(page_title="Echo", page_icon="🌊", layout="wide")

# UI STYLING (The Ocean Look)
st.markdown("""
<style>
    .stApp { background: linear-gradient(to bottom right, #0f2027, #203a43, #2c5364); color: white; }
    .stChatMessage { background-color: rgba(255, 255, 255, 0.05); border-radius: 15px; border: 1px solid rgba(255, 255, 255, 0.1); }
    div[data-testid="stAlert"] { background: rgba(255, 255, 255, 0.1); border-radius: 12px; color: white; }
    .slot-box { padding: 10px; border-radius: 10px; margin-bottom: 5px; border-left: 5px solid #555; background: rgba(0,0,0,0.2); }
    .slot-filled { border-left: 5px solid #00ff96; background: rgba(0, 255, 150, 0.1); }
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
# 2. CALENDAR LOGIC (Time Slots)
# ==========================================

# A. Initialize the Day's Timeline (The Calendar)
if "echo_calendar" not in st.session_state:
    st.session_state.echo_calendar = [
        {"time": "09:00 AM", "task": "Morning Routine", "locked": True}, # Done
        {"time": "11:00 AM", "task": None, "locked": False}, # Empty
        {"time": "01:00 PM", "task": None, "locked": False}, # Empty
        {"time": "03:00 PM", "task": None, "locked": False}, # Empty
        {"time": "05:00 PM", "task": None, "locked": False}, # Empty
    ]

# B. The Backlog (Tasks waiting to be scheduled)
if "echo_backlog" not in st.session_state:
    st.session_state.echo_backlog = [
        "Calculus: Derivatives",
        "Physics: Lab Report",
        "History: Read Chapter 4",
        "Coding: Debug Project"
    ]

def schedule_next_task():
    """Finds the first EMPTY slot and fills it from backlog."""
    # 1. Get task from backlog
    if not st.session_state.echo_backlog:
        return None, "Backlog is empty!"
    
    task_name = st.session_state.echo_backlog[0] # Peek at top task

    # 2. Find first empty slot in calendar
    for slot in st.session_state.echo_calendar:
        if slot["task"] is None:
            # Found empty slot! Fill it.
            slot["task"] = task_name
            st.session_state.echo_backlog.pop(0) # Remove from backlog
            return task_name, slot["time"]
            
    return None, "No time slots left today!"

def clear_upcoming_schedule():
    """Clears all future tasks (Burnout Mode)."""
    cleared_count = 0
    for slot in st.session_state.echo_calendar:
        # Only clear unlocked tasks that have content
        if not slot["locked"] and slot["task"] is not None:
            # Move back to backlog
            st.session_state.echo_backlog.insert(0, slot["task"])
            slot["task"] = None
            cleared_count += 1
    return cleared_count

# ==========================================
# 3. THE UI
# ==========================================
st.title("🌊 Echo")
st.markdown("### The calendar that breathes with you.")

col1, col2 = st.columns([2, 1])

# --- LEFT COLUMN: Chat ---
with col1:
    st.subheader("💭 The Vibe Check")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.messages.append({"role": "assistant", "content": "I'm looking at your timeline. How are you feeling?"})

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
            1. If MOTIVATED: Return JSON {{ "action": "FILL_SCHEDULE", "reply": "Great! Filling your empty slots." }}
            2. If STRESSED: Return JSON {{ "action": "CLEAR_SCHEDULE", "reply": "Understood. Clearing the afternoon so you can rest." }}
            3. Otherwise: {{ "action": "NONE", "reply": "Tell me more." }}
            """
            response = model.generate_content(prompt)
            text = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(text)
            
            action = data.get('action')
            bot_reply = data.get('reply')

            if action == "FILL_SCHEDULE":
                task, time = schedule_next_task()
                if task:
                    st.toast(f"Scheduled '{task}' for {time}", icon="📅")
                else:
                    bot_reply += " (Calendar is full!)"
                    
            elif action == "CLEAR_SCHEDULE":
                count = clear_upcoming_schedule()
                if count > 0:
                    st.toast(f"Cleared {count} slots.", icon="💨")
                else:
                    bot_reply += " (Nothing to clear)."

            st.session_state.messages.append({"role": "assistant", "content": bot_reply})
            with st.chat_message("assistant"):
                st.markdown(bot_reply)
            
            st.rerun()
                
        except Exception as e:
            st.error(f"Error: {e}")

# --- RIGHT COLUMN: Time-Block Calendar ---
with col2:
    st.subheader("📅 Today's Timeline")
    
    # Render the Time Slots
    for slot in st.session_state.echo_calendar:
        time = slot["time"]
        task = slot["task"]
        
        if task:
            # FILLED SLOT (Green/Blue)
            st.info(f"**{time}** | {task}")
        else:
            # EMPTY SLOT (Grey/Ghost)
            st.markdown(f"""
            <div style="padding:10px; border-radius:10px; margin-bottom:10px; background:rgba(255,255,255,0.05); color: #888;">
                {time} | <i>Free Slot</i>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.caption(f"Waiting in Backlog: {len(st.session_state.echo_backlog)} tasks")


