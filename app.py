import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from groq import Groq
import json
from datetime import datetime

# ==========================================
# 1. SETUP & OCEAN UI
# ==========================================
st.set_page_config(page_title="Echo", page_icon="🌊", layout="wide")

st.markdown("""
<style>
    /* OCEAN THEME */
    .stApp { background: linear-gradient(to bottom right, #0f2027, #203a43, #2c5364); color: white; }
    
    /* CHAT BUBBLES */
    .stChatMessage { background-color: rgba(255, 255, 255, 0.05); border-radius: 15px; border: 1px solid rgba(255, 255, 255, 0.1); }
    
    /* GLASS CARDS */
    div[data-testid="stAlert"] { background: rgba(255, 255, 255, 0.1); border-radius: 12px; color: white; border: 1px solid rgba(255,255,255,0.2); }
    .stTextInput input { background-color: rgba(0, 0, 0, 0.3); color: white; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.2); }
    
    /* BUTTONS */
    .stButton button { background: linear-gradient(45deg, #00c6ff, #0072ff); color: white; border-radius: 20px; border: none; font-weight: bold; }
    
    /* CUSTOM SLOTS */
    .slot-box { padding: 12px; border-radius: 10px; margin-bottom: 8px; border: 1px dashed #555; background: rgba(0,0,0,0.2); color: #aaa; }
    .slot-filled { border-left: 5px solid #00c6ff; background: rgba(0, 198, 255, 0.1); color: white; border-style: solid; border-color: rgba(255,255,255,0.1); }
</style>
""", unsafe_allow_html=True)

# 🔑 API KEY CHECKS
if "GROQ_API_KEY" not in st.secrets:
    st.error("🚨 GROQ_API_KEY is missing in Secrets!")
    st.stop()

# Initialize Groq (Llama 3)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# ==========================================
# 2. FIREBASE CONNECTION
# ==========================================
if not firebase_admin._apps:
    try:
        if "firebase" in st.secrets:
            key_dict = dict(st.secrets["firebase"])
            # Auto-fix newlines
            if "\\n" in key_dict["private_key"]:
                key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
            
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
        else:
            st.error("Secrets missing [firebase] section.")
            st.stop()
    except Exception as e:
        st.error(f"🔥 Firebase Error: {e}")
        st.stop()

try:
    db = firestore.client()
except:
    db = None

# ==========================================
# 3. DATABASE FUNCTIONS (Real Cloud Data)
# ==========================================

def get_backlog():
    """Fetch pending tasks"""
    if db is None: return []
    try:
        docs = db.collection('echo_backlog').order_by('created_at').stream()
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
    except: return []

def get_calendar_slots():
    """Fetch calendar slots"""
    if db is None: return []
    try:
        docs = db.collection('echo_calendar').order_by('time_slot').stream()
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
    except: return []

def add_to_backlog(task_name):
    if db is None: return
    db.collection('echo_backlog').add({
        "task": task_name, 
        "created_at": datetime.now().isoformat()
    })

def delete_backlog_item(doc_id):
    if db is None: return
    db.collection('echo_backlog').document(doc_id).delete()

# --- THE MAGIC MOVE LOGIC ---

def move_backlog_to_calendar():
    """Moves Top Backlog Item -> First Empty Slot"""
    backlog = get_backlog()
    if not backlog: return None, "Backlog empty"
    
    # Get current filled slots
    filled_slots = [s['time_slot'] for s in get_calendar_slots()]
    
    # Define the day's structure
    all_slots = ["09:00 AM", "11:00 AM", "01:00 PM", "03:00 PM", "05:00 PM"]
    
    target_slot = None
    for slot in all_slots:
        if slot not in filled_slots:
            target_slot = slot
            break
            
    if not target_slot: return None, "Calendar Full"

    # Move logic
    top_task = backlog[0]
    
    # 1. Add to Calendar
    db.collection('echo_calendar').add({
        "task": top_task['task'],
        "time_slot": target_slot,
        "created_at": datetime.now().isoformat()
    })
    
    # 2. Delete from Backlog
    db.collection('echo_backlog').document(top_task['id']).delete()
    
    return top_task['task'], target_slot

def clear_calendar_to_backlog():
    """Moves ALL unlocked calendar items back to backlog"""
    slots = get_calendar_slots()
    count = 0
    for slot in slots:
        # 1. Add back to Backlog
        db.collection('echo_backlog').add({
            "task": slot['task'],
            "created_at": datetime.now().isoformat()
        })
        # 2. Delete from Calendar
        db.collection('echo_calendar').document(slot['id']).delete()
        count += 1
    return count

# ==========================================
# 4. GROQ AI ENGINE
# ==========================================
def call_groq(user_text):
    try:
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {
                    "role": "system",
                    "content": """You are Echo, a mood-adaptive scheduler.
                    1. If user is MOTIVATED/ENERGETIC: Return JSON { "action": "FILL", "reply": "Great! Moving tasks to your schedule." }
                    2. If user is STRESSED/TIRED: Return JSON { "action": "CLEAR", "reply": "Understood. Clearing schedule for rest." }
                    3. Otherwise: { "action": "NONE", "reply": "Tell me more." }
                    RETURN ONLY RAW JSON."""
                },
                {"role": "user", "content": user_text}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return completion.choices[0].message.content
    except Exception as e:
        return None

# ==========================================
# 5. THE UI
# ==========================================
st.title("🌊 Echo")
st.markdown("### The calendar that breathes with you.")

col1, col2 = st.columns([2, 1])

# --- LEFT: CHAT ---
with col1:
    st.subheader("💭 The Vibe Check")
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "I'm connected to Firebase + Groq. How is your energy?"}]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_input := st.chat_input("Ex: 'I am motivated'"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.spinner("Echo is syncing..."):
            
            # CALL GROQ
            raw_json = call_groq(user_input)
            
            if raw_json:
                try:
                    data = json.loads(raw_json)
                    action = data.get('action')
                    bot_reply = data.get('reply')

                    if action == "FILL":
                        task, slot = move_backlog_to_calendar()
                        if task: st.toast(f"Scheduled '{task}' at {slot}", icon="📅")
                        else: bot_reply += " (No tasks or slots available)."
                    elif action == "CLEAR":
                        count = clear_calendar_to_backlog()
                        if count > 0: st.toast(f"Cleared {count} tasks.", icon="💨")

                    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
                    with st.chat_message("assistant"):
                        st.markdown(bot_reply)
                    st.rerun()
                except:
                    st.error("Echo got confused.")
            else:
                st.error("AI Connection Failed.")

# --- RIGHT: CALENDAR & BACKLOG ---
with col2:
    st.subheader("📅 Today's Timeline")
    
    # Get Real Data from Firebase
    calendar_items = get_calendar_slots()
    slot_map = {item['time_slot']: item['task'] for item in calendar_items}
    
    # Hardcoded Time Slots for Visual Structure
    all_slots = ["09:00 AM", "11:00 AM", "01:00 PM", "03:00 PM", "05:00 PM"]
    
    for slot_time in all_slots:
        if slot_time in slot_map:
            # Filled Slot (Blue)
            st.markdown(f"""
            <div class="slot-box slot-filled">
                <b>{slot_time}</b> | {slot_map[slot_time]}
            </div>
            """, unsafe_allow_html=True)
        else:
            # Empty Slot (Ghost)
            st.markdown(f"""
            <div class="slot-box">
                {slot_time} | <i>Free Slot</i>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("📝 Cloud Backlog")
    
    # Manual Add
    with st.form("add_task", clear_on_submit=True):
        new_task = st.text_input("Add task:", placeholder="E.g. Chemistry Test")
        if st.form_submit_button("➕ Add"):
            if new_task:
                add_to_backlog(new_task)
                st.rerun()

    # Backlog List
    backlog_items = get_backlog()
    if backlog_items:
        for item in backlog_items:
            c1, c2 = st.columns([5, 1])
            c1.code(item['task'])
            if c2.button("❌", key=item['id']):
                delete_backlog_item(item['id'])
                st.rerun()
    else:
        st.caption("Backlog is empty!")














