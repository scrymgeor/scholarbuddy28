import streamlit as st
import google.generativeai as genai
import json
from datetime import datetime

# ==========================================
# 1. SETUP
# ==========================================
st.set_page_config(page_title="ECHO", page_icon="", layout="wide")

# 🔑 SECURE GEMINI LOGIN
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    st.error("🚨 Gemini API Key is missing in Secrets!")
    st.stop()

# ==========================================
# 2. DATABASE LOGIC (Backlog + Schedule)
# ==========================================
# 1. Active Schedule
if "echo_schedule" not in st.session_state:
    st.session_state.echo_schedule = []

# 2. Pending Backlog (Pre-filled)
if "echo_backlog" not in st.session_state:
    st.session_state.echo_backlog = [
        "Math: Calculus Chapter 4",
        "Physics: Thermodynamics Lab",
        "History: Write Essay",
    ]

def add_task_from_backlog():
    """Moves a task from Backlog -> Schedule"""
    if st.session_state.echo_backlog:
        task = st.session_state.echo_backlog.pop(0)
        st.session_state.echo_schedule.append({
            "summary": task,
            "created_at": datetime.now().isoformat()
        })
        return task
    return None

def clear_task_to_backlog():
    """Moves a task from Schedule -> Backlog"""
    if st.session_state.echo_schedule:
        task_obj = st.session_state.echo_schedule.pop()
        task_name = task_obj['summary']
        st.session_state.echo_backlog.insert(0, task_name)
        return task_name
    return None

# ==========================================
# 3. THE UI
# ==========================================
st.title("ECHO ")
st.markdown("### Your schedule echoes your state of mind.")

col1, col2 = st.columns([2, 1])

# --- LEFT COLUMN: Chat with AI ---
with col1:
    st.subheader("💭 The Vibe Check")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.messages.append({"role": "assistant", "content": "I am ready. How is your energy?"})

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_input := st.chat_input("Ex: 'I am motivated'"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        try:
            prompt = f"""
            Analyze mood: "{user_input}".
            Return JSON: {{ "action": "CLEAR" or "ADD", "reply": "Short advice" }}
            """
            response = model.generate_content(prompt)
            text = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(text)
            
            action = data.get('action')
            bot_reply = data.get('reply')

            if action == "ADD":
                task = add_task_from_backlog()
                if task:
                    st.toast(f"Moved '{task}' to Schedule!", icon="🔥")
                else:
                    bot_reply += " (Your backlog is empty! Add tasks on the right.)"
                    
            elif action == "CLEAR":
                removed = clear_task_to_backlog()
                if removed:
                    st.toast(f"Saved '{removed}' for later.", icon="💤")
                else:
                    bot_reply += " (Schedule is already clear)."

            st.session_state.messages.append({"role": "assistant", "content": bot_reply})
            with st.chat_message("assistant"):
                st.markdown(bot_reply)
            
            st.rerun()
                
        except Exception as e:
            st.error(f"Thinking... {e}")

# --- RIGHT COLUMN: Manual Controls ---
with col2:
    st.subheader("📅 Live Schedule")
    
    # 1. ACTIVE SCHEDULE
    if st.session_state.echo_schedule:
        for task in st.session_state.echo_schedule:
            st.success(f"**⏰ NOW:** {task['summary']}")
    else:
        st.info("You are resting. No active tasks.")

    st.markdown("---")
    
    # 2. PENDING TASKS (Backlog)
    st.subheader("📝 Pending Tasks")
    
    # Input to ADD a new task
    with st.form("add_task_form", clear_on_submit=True):
        new_task_text = st.text_input("Add new task:", placeholder="E.g., Buy Groceries")
        submitted = st.form_submit_button("➕ Add to List")
        if submitted and new_task_text:
            st.session_state.echo_backlog.append(new_task_text)
            st.rerun()

    # List of tasks with DELETE buttons
    if st.session_state.echo_backlog:
        for i, item in enumerate(st.session_state.echo_backlog):
            c1, c2 = st.columns([4, 1])
            c1.code(item)
            # The delete button
            if c2.button("❌", key=f"del_{i}"):
                st.session_state.echo_backlog.pop(i)
                st.rerun()
    else:
        st.caption("No pending tasks! Good job.")

