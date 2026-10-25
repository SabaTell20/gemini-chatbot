# app.py - the main chat page. Run with:  streamlit run app.py

import uuid                              # makes unique session ids
import streamlit as st                   # the web page library
from google import genai                 # Gemini library
from google.genai import types           # helper classes for Gemini settings
import db                                # our MySQL functions (db.py)
from config import API_KEY, MODEL        # our settings (config.py)

# Keep this prompt the SAME every time so Gemini's implicit caching can reuse it
SYSTEM_PROMPT = "You are a helpful assistant. Answer clearly and simply."

st.set_page_config(page_title="Gemini Chatbot")   # browser tab title
db.create_tables()                                # make sure the tables exist
client = genai.Client(api_key=API_KEY)            # connect to Gemini

# Streamlit re-runs this whole file on every click, so we remember things in session_state.
# If there is no current session yet, start a new one with a random unique id.
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.title("Chats")

    if st.button("➕ New chat"):                              # new chat button
        st.session_state.session_id = str(uuid.uuid4())      # brand new empty session
        st.rerun()                                           # redraw the page

    # The three feature switches. They are False (off) until the user turns them on.
    use_search = st.toggle("Google Search", key="use_search")
    use_thinking = st.toggle("Thinking", key="use_thinking")
    use_streaming = st.toggle("Streaming", key="use_streaming")

    st.page_link("pages/Pricing.py", label="💰 Token pricing")   # link to the second page
    st.divider()

    # One row per saved session: a button with its title, and a delete button
    for session_id, title in db.list_sessions():
        col1, col2 = st.columns([4, 1])                       # wide column + narrow column
        if col1.button(title, key="open_" + session_id):      # open this session
            st.session_state.session_id = session_id
            st.rerun()
        if col2.button("🗑", key="del_" + session_id):        # soft delete this session
            db.delete_session(session_id)
            if session_id == st.session_state.session_id:     # if we deleted the open one...
                st.session_state.session_id = str(uuid.uuid4())   # ...start a fresh chat
            st.rerun()

# ---------------- CHAT AREA ----------------
st.title("Gemini Chatbot")
session_id = st.session_state.session_id         # shortcut name for the current session
history = db.load_messages(session_id)           # list of (role, message) from MySQL

for role, message in history:                    # show every old message
    with st.chat_message(role):                  # role is "user" or "assistant"
        st.write(message)

prompt = st.chat_input("Type your message...")   # the box at the bottom

if prompt:                                       # runs only when the user pressed Enter
    with st.chat_message("user"):
        st.write(prompt)                         # show the new question right away

    # 1. Turn our history into the format Gemini wants (its bot role is called "model")
    contents = []
    for role, message in history:
        gemini_role = "model" if role == "assistant" else "user"
        contents.append(types.Content(role=gemini_role, parts=[types.Part(text=message)]))
    contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))

    # 2. Build the settings that depend on the switches
    tools = None                                              # no tools = no Google
    if use_search:
        tools = [types.Tool(google_search=types.GoogleSearch())]   # allow Google Search
    level = "high" if use_thinking else "low"                 # thinking on = high, off = low
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=tools,
        thinking_config=types.ThinkingConfig(thinking_level=level),
    )

    # 3. Ask Gemini
    try:
        with st.chat_message("assistant"):
            answer = ""                                       # the full answer will be built here
            usage = None                                      # token counts will be stored here

            if use_streaming:                                 # STREAMING: show text piece by piece
                box = st.empty()                              # an empty spot we keep overwriting
                stream = client.models.generate_content_stream(
                    model=MODEL, contents=contents, config=config
                )
                for chunk in stream:                          # each chunk is a small piece
                    if chunk.text:                            # some chunks have no text
                        answer += chunk.text
                        box.write(answer)
                    if chunk.usage_metadata:                  # keep the latest token counts
                        usage = chunk.usage_metadata
            else:                                             # NOT STREAMING: wait for everything
                with st.spinner("Waiting for Gemini..."):
                    response = client.models.generate_content(
                        model=MODEL, contents=contents, config=config
                    )
                answer = response.text
                usage = response.usage_metadata
                st.write(answer)

        # 4. Save both messages in MySQL
        db.save_message(session_id, prompt, "user")
        answer_id = db.save_message(session_id, answer, "assistant")

        # 5. Save the token counts (the "or 0" turns None into 0)
        cached = usage.cached_content_token_count or 0
        input_tokens = (usage.prompt_token_count or 0) - cached   # prompt count includes cached ones
        output_tokens = usage.candidates_token_count or 0
        thinking_tokens = usage.thoughts_token_count or 0
        db.save_usage(session_id, answer_id, input_tokens, cached, output_tokens, thinking_tokens)

        st.rerun()                                            # redraw so the sidebar shows the new chat

    except Exception as error:                                # if anything fails, show the error
        st.error(f"Something went wrong: {error}")
