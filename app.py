import os
import uuid
import streamlit as st
from google import genai
from google.genai import types
import db
from config import API_KEY, MODEL

SYSTEM_PROMPT = "You are a helpful assistant. Answer clearly and simply."
UPLOAD_FOLDER = "uploads"
FILE_TYPES = ["png", "jpg", "jpeg", "webp", "pdf", "mp3", "wav", "ogg", "flac", "aac"]

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
st.set_page_config(page_title="Gemini Chatbot")
db.create_tables()
client = genai.Client(api_key=API_KEY)


def save_file(uploaded_file):
    extension = os.path.splitext(uploaded_file.name)[1]
    file_path = os.path.join(UPLOAD_FOLDER, uuid.uuid4().hex + extension)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getvalue())
    mime_type = uploaded_file.type
    if mime_type == "audio/mpeg":
        mime_type = "audio/mp3"
    return (uploaded_file.name, mime_type, file_path)


def show_attachments(files):
    for file_name, mime_type, file_path in files:
        if mime_type.startswith("image/"):
            st.image(file_path, caption=file_name)
        elif mime_type.startswith("audio/"):
            st.audio(file_path, format=mime_type)
        else:
            st.write("📄 " + file_name)


def make_parts(text, files):
    parts = []
    for file_name, mime_type, file_path in files:
        with open(file_path, "rb") as f:
            parts.append(types.Part.from_bytes(data=f.read(), mime_type=mime_type))
    parts.append(types.Part(text=text))
    return parts


def stream_text(stream, holder):
    for chunk in stream:
        if chunk.usage_metadata:
            holder["usage"] = chunk.usage_metadata
        if chunk.text:
            yield chunk.text


def has_type(files, prefix):
    for file_name, mime_type, file_path in files:
        if mime_type.startswith(prefix):
            return True
    return False


def save_usage_from(session_id, message_id, usage):
    cached = usage.cached_content_token_count or 0
    input_tokens = (usage.prompt_token_count or 0) - cached
    output_tokens = usage.candidates_token_count or 0
    thinking_tokens = usage.thoughts_token_count or 0
    db.save_usage(session_id, message_id, input_tokens, cached, output_tokens, thinking_tokens)


def transcribe(file_path, mime_type):
    with open(file_path, "rb") as f:
        audio = types.Part.from_bytes(data=f.read(), mime_type=mime_type)
    response = client.models.generate_content(
        model=MODEL,
        contents=[audio, "Transcribe this audio word for word. Return only the transcript."],
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="low")
        ),
    )
    return response.text, response.usage_metadata


def save_feedback(message_id):
    value = st.session_state["fb_" + str(message_id)]
    feedback = None
    if value == 1:
        feedback = "like"
    elif value == 0:
        feedback = "dislike"
    db.save_feedback(message_id, feedback)


if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

with st.sidebar:
    st.title("Chats")

    if st.button("➕ New chat"):
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    use_search = st.toggle("Google Search", key="use_search")
    use_thinking = st.toggle("Thinking", key="use_thinking")
    use_streaming = st.toggle("Streaming", key="use_streaming")

    st.page_link("pages/Pricing.py", label="💰 Token pricing")
    st.divider()

    for session_id, title in db.list_sessions():
        col1, col2 = st.columns([4, 1])
        if col1.button(title, key="open_" + session_id):
            st.session_state.session_id = session_id
            st.rerun()
        if col2.button("🗑", key="del_" + session_id):
            db.delete_session(session_id)
            if session_id == st.session_state.session_id:
                st.session_state.session_id = str(uuid.uuid4())
            st.rerun()

st.title("Gemini Chatbot")
session_id = st.session_state.session_id
history = db.load_messages(session_id)

attachments = {}
for message_id, file_name, mime_type, file_path in db.load_attachments(session_id):
    if message_id not in attachments:
        attachments[message_id] = []
    attachments[message_id].append((file_name, mime_type, file_path))

for message_id, role, message, transcription, feedback in history:
    with st.chat_message(role):
        show_attachments(attachments.get(message_id, []))
        if transcription:
            st.caption("🎤 " + transcription)
        st.write(message)
        if role == "assistant":
            default = None
            if feedback == "like":
                default = 1
            elif feedback == "dislike":
                default = 0
            st.feedback(
                "thumbs",
                key="fb_" + str(message_id),
                default=default,
                on_change=save_feedback,
                args=(message_id,),
            )

chat_input = st.chat_input(
    "Type a message, attach a file or record a voice memo...",
    accept_file="multiple",
    file_type=FILE_TYPES,
    accept_audio=True,
)

if chat_input:
    text = chat_input.text or "Please look at the attached file."

    uploaded = list(chat_input.files)
    if chat_input.audio:
        uploaded.append(chat_input.audio)

    new_files = []
    for uploaded_file in uploaded:
        new_files.append(save_file(uploaded_file))

    with st.chat_message("user"):
        show_attachments(new_files)
        st.write(text)

    contents = []
    for message_id, role, message, transcription, feedback in history:
        gemini_role = "model" if role == "assistant" else "user"
        parts = make_parts(message, attachments.get(message_id, []))
        contents.append(types.Content(role=gemini_role, parts=parts))
    contents.append(types.Content(role="user", parts=make_parts(text, new_files)))

    tools = None
    if use_search:
        tools = [types.Tool(google_search=types.GoogleSearch())]
    level = "high" if use_thinking else "low"
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=tools,
        thinking_config=types.ThinkingConfig(thinking_level=level),
    )

    try:
        with st.chat_message("assistant"):
            if use_streaming:
                holder = {"usage": None}
                stream = client.models.generate_content_stream(
                    model=MODEL, contents=contents, config=config
                )
                answer = st.write_stream(stream_text(stream, holder))
                usage = holder["usage"]
            else:
                with st.spinner("Waiting for Gemini..."):
                    response = client.models.generate_content(
                        model=MODEL, contents=contents, config=config
                    )
                answer = response.text
                usage = response.usage_metadata
                st.write(answer)

        if len(history) == 0:
            db.create_session(session_id, text[:30])

        user_id = db.save_message(session_id, text, "user")
        for file_name, mime_type, file_path in new_files:
            db.save_attachment(session_id, user_id, file_name, mime_type, file_path)

        answer_id = db.save_message(session_id, answer, "assistant")
        db.save_assistant_message(answer_id, session_id, MODEL)
        save_usage_from(session_id, answer_id, usage)

        db.save_sender_params(
            user_id,
            use_thinking,
            use_streaming,
            use_search,
            has_type(new_files, "audio/"),
            has_type(new_files, "image/"),
            has_type(new_files, "application/pdf"),
        )

        transcripts = []
        for file_name, mime_type, file_path in new_files:
            if mime_type.startswith("audio/"):
                with st.spinner("Transcribing voice memo..."):
                    transcript, transcript_usage = transcribe(file_path, mime_type)
                transcripts.append(transcript)
                save_usage_from(session_id, user_id, transcript_usage)
        if transcripts:
            db.save_transcription(user_id, "\n".join(transcripts))

        st.rerun()

    except Exception as error:
        st.error(f"Something went wrong: {error}")
