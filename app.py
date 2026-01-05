import streamlit as st
import google.generativeai as genai
from google_setup import get_calendar_service # Imports your login script
from datetime import datetime, timedelta
import json

# ==========================================
# 1. CONFIGURATION
# ==========================================
# 🔑 PASTE YOUR GEMINI API KEY BELOW inside the quotes
GOOGLE_API_KEY = "AIzaSyBt28XGAQXSwiq9sTbedtcSbRnzbhQ1cCc"

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Connect to Calendar using your previous script
try:
    calendar_service = get_calendar_service()
    st.toast("Connected to Google Calendar ✅")
except:
    st.error("Login failed. Delete token.json and try again.")

# ==========================================
# 2. CALENDAR FUNCTIONS (The "Hands")
# ==========================================
def get_upcoming_events():
    """Fetch next 5 events to show the user."""
    now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
    events_result = calendar_service.events().list(
        calendarId='primary', timeMin=now,
        maxResults=5, singleEvents=True,
        orderBy='startTime').execute()
    return events_result.get('items', [])

def add_study_session(topic):
    """Adds a 45-min study block 1 hour from now."""
    start_time = datetime.now() + timedelta(minutes=60)
    end_time = start_time + timedelta(minutes=45)
    
    event = {
        'summary': f'🧘 Zen Study: {topic}',
        'description': 'Scheduled by ZenScholar based on your mood.',
        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'UTC'},
        'end': {'dateTime': end_time.isoformat(), 'timeZone': 'UTC'},
        'colorId': '10' # Green color
    }
    calendar_service.events().insert(calendarId='primary', body=event).execute()

def clear_schedule():
    """Deletes the next event (Simulating stress relief)."""
    events = get_upcoming_events()
    if events:
        event_id = events[0]['id']
        calendar_service.events().delete(calendarId='primary', eventId=event_id).execute()
        return events[0]['summary']
    return None

# ==========================================
# 3. THE UI (Streamlit)
# ==========================================
st.set_page_config(page_title="ZenScholar", page_icon="🧘", layout="wide")

# Title Section
st.title("🧘 ZenScholar")
st.markdown("### The mood-adaptive study companion.")

# Create two columns: Chat (Left) and Calendar (Right)
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("#### 💬 How are you feeling?")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    if user_input := st.chat_input("Ex: 'I am super motivated' or 'I am so stressed'"):
        # 1. Show User Message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # 2. GEMINI BRAIN LOGIC
        with st.spinner("ZenScholar is thinking..."):
            system_prompt = f"""
            You are a calendar assistant. Analyze this text: "{user_input}"
            
            1. Determine the user's MOOD (Stressed or Motivated).
            2. If Stressed: Return JSON {{ "action": "CLEAR", "reply": "I hear you. I've cleared your next task. Go rest." }}
            3. If Motivated: Return JSON {{ "action": "ADD", "topic": "Deep Work", "reply": "Let's use this energy! I added a Deep Work session." }}
            4. If Unsure: Return JSON {{ "action": "NONE", "reply": "Tell me more about how you feel." }}
            
            Return ONLY RAW JSON. No markdown.
            """
            
            response = model.generate_content(system_prompt)
            
            try:
                # Clean JSON
                text = response.text.strip().replace('```json', '').replace('```', '')
                data = json.loads(text)
                
                bot_reply = data['reply']
                action = data.get('action')

                # 3. PERFORM ACTION
                if action == "ADD":
                    add_study_session(data.get('topic', 'Study'))
                    st.toast("📅 Calendar Updated: Added Session!", icon="✅")
                    
                elif action == "CLEAR":
                    removed_event = clear_schedule()
                    if removed_event:
                        st.toast(f"🗑️ Removed: {removed_event}", icon="📉")
                    else:
                        bot_reply = "Your schedule is already empty, but take a break anyway!"

                # 4. Show Bot Reply
                st.session_state.messages.append({"role": "assistant", "content": bot_reply})
                with st.chat_message("assistant"):
                    st.markdown(bot_reply)
                    
            except Exception as e:
                st.error(f"Error parsing Gemini: {e}")

with col2:
    st.markdown("#### 📅 Live Schedule")
    if st.button("🔄 Refresh Calendar"):
        pass # Just reruns the script
        
    events = get_upcoming_events()
    if not events:
        st.info("No upcoming events found.")
    else:
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            # Clean up time string
            time_str = start[11:16] if 'T' in start else start
            st.success(f"**{time_str}** | {event['summary']}")