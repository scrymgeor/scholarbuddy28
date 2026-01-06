import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json
import requests # <--- We are using this instead of the Google Library
from datetime import datetime

# ==========================================
# 1. SETUP & STYLING
# ==========================================
st.set_page_config(page_title="Echo", page_icon="🌊", layout="wide")

st.markdown("""
<style>
    .stApp { background: linear-gradient(to bottom right, #0f2027, #203a43, #2c5364); color: white; }
    .stChatMessage { background-color: rgba(255, 255, 255, 0.05); border-radius: 15px; border: 1px solid rgba(255, 255, 255, 0.1); }
    div[data-testid="stAlert"] { background: rgba(255, 255, 255, 0.1); border-radius: 12px; color: white; border: 1px solid rgba(255,255,255,0.2); }
    .stTextInput input { background-color: rgba(0, 0, 0, 0.3); color: white; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.2); }
    .stButton button { background: linear-gradient(45deg, #00c6ff, #0072ff); color: white; border-radius: 20px; border: none; }
</style>
""", unsafe_allow_html=True)

# 🔑 API KEY CHECK
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🚨 Google API Key is missing in Secrets!")
    st.stop()

API_KEY = st.secrets["GOOGLE_API_KEY"]

# ==========================================
# 2. THE "DIRECT" AI CALL (Bypasses Library)
# ==========================================
def call_gemini_flash(prompt_text):
    """
    Sends a direct HTTP request to Gemini 1.5 Flash.
    This works even if the Python library is broken/old.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{
            "parts": [{"text": prompt_text}]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        
        # Check for quota errors
        if response.status_code == 429:
            return None, "QUOTA_EXCEEDED"
            
        if response.status_code != 200:
            return None, f"Error {response.status_code}: {response.text}"
            
        # Parse the JSON response
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text'], "SUCCESS"
        
    except Exception as e:
        return None, str(e)

# ==========================================
# 3. FIREBASE CONNECTION
# ==========================================
if not firebase_admin._apps:
    try:
        if "firebase" in st.secrets:
            key_dict = dict(st.secrets["firebase"])
            # Fix newlines manually just in case
            if "\\n" in key_dict["private_key"]:
                key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
        else:
            st.error("Secrets are missing the [firebase] section.")
            st.stop()
    except Exception as e:
        st.error(f"🔥 Firebase Connection Failed: {e}")
        st.stop()

try:
    db = firestore.client()
except:
    db = None

# ==========================================
# 4. DATABASE FUNCTIONS
# ==========================================
def get_backlog():
    if db is None: return []
    try:
        docs = db.collection('echo_backlog').order_by('created_at').stream()
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
    except:
        return []

def get_calendar_slots():
    if db is None: return []
    try:
        docs = db.collection('echo_calendar').order_by('time_slot').stream()
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
    except:
        return []

def add_to_backlog(task_name):
    if db is None: return
    db.collection('echo_backlog').add({
        "task": task_name,
        "created_at": datetime.now().isoformat()
    })

def move_backlog_to_calendar():
    backlog = get_backlog()
    if not backlog: return None, "Backlog empty"
    
    active_slots = [s['time_slot'] for s in get_calendar_slots()]
    all_slots = ["09:00 AM", "11:00 AM", "01:00 PM", "03:00 PM", "05:00 PM"]
    
    target_slot = None
    for slot in all_slots:
        if slot not in active_slots:
            target_slot = slot
            break
            
    if not target_slot: return None, "Calendar Full"

    top_task = backlog[0]
    db.collection('echo_backlog').document(top_task['id']).delete()
    db.collection('echo_calendar').add({
        "task": top_task['task'],
        "time_slot": target_slot,
        "created_at": datetime.now().isoformat()
    })
    return top_task['task'], target_slot

def clear_calendar_to_backlog():
    slots = get_calendar_slots()
    count = 0
    for slot in slots:
        db.collection('echo_backlog').add({
            "task": slot['task'],
            "created_at": datetime.now().isoformat()
        })
        db.collection('echo_calendar').document(slot['id']).delete()
        count += 1
    return count

def delete_backlog_item(doc_id):
    db.collection('echo_backlog').document(doc_id).delete()

# ==========================================
# 5. THE UI
# ==========================================
st.title("🌊 Echo")
st.markdown("### The calendar that breathes with you.")

col1, col2 = st.columns([2, 1])

# --- LEFT COLUMN: Chat ---
with col1:
    st.subheader("💭 The Vibe Check")
    
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Connected to Cloud. How is your energy?"}]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_input := st.chat_input("Ex: 'I am motivated'"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.spinner("Echo is syncing..."):
            prompt = f"""
            User says: "{user_input}"
            1. If MOTIVATED: Return JSON {{ "action": "FILL", "reply": "Great! Moving tasks to your schedule." }}
            2. If STRESSED: Return JSON {{ "action": "CLEAR", "reply": "Understood. Clearing schedule for rest." }}
            3. Otherwise: {{ "action": "NONE", "reply": "Tell me more." }}
            RETURN ONLY JSON.
            """
            
            # CALL DIRECT API
            raw_response, status = call_gemini_flash(prompt)
            
            if status == "SUCCESS":
                try:
                    text = raw_response.replace('```json', '').replace('```', '').strip()
                    data = json.loads(text)
                    
                    action = data.get('action')
                    bot_reply = data.get('reply')

                    if action == "FILL":
                        task, slot = move_backlog_to_calendar()
                        if task: st.toast(f"Scheduled '{task}' at {slot}", icon="📅")
                        else: bot_reply += " (No tasks or no slots available)."
                            
                    elif action == "CLEAR":
                        count = clear_calendar_to_backlog()
                        if count > 0: st.toast(f"Cleared {count} tasks.", icon="💨")

                    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
                    with st.chat_message("assistant"):
                        st.markdown(bot_reply)
                    
                    st.rerun()
                except:
                    st.error("Error parsing AI response.")
            elif status == "QUOTA_EXCEEDED":
                 st.error("⚠️ Quota Limit. Please wait 1 minute.")
            else:
                 st.error(f"API Error: {status}")

# --- RIGHT COLUMN: Real DB Data ---
with col2:
    st.subheader("📅 Today's Timeline")
    
    calendar_items = get_calendar_slots()
    slot_map = {item['time_slot']: item['task'] for item in calendar_items}
    all_slots = ["09:00 AM", "11:00 AM", "01:00 PM", "03:00 PM", "05:00 PM"]
    
    for slot_time in all_slots:
        if slot_time in slot_map:
            st.info(f"**{slot_time}** | {slot_map[slot_time]}")
        else:
             st.markdown(f"""<div style="padding:10px; border-radius:10px; margin-bottom:10px; background:rgba(255,255,255,0.05); color: #aaa; border: 1px dashed #555;">{slot_time} | <i>Free Slot</i></div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("📝 Cloud Backlog")
    
    with st.form("add_task", clear_on_submit=True):
        new_task = st.text_input("Add task:", placeholder="E.g. Chemistry Test")
        if st.form_submit_button("➕ Add"):
            if new_task:
                add_to_backlog(new_task)
                st.rerun()

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













