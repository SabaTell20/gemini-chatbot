# db.py - every function that talks to MySQL lives here

import mysql.connector  # the package that lets Python talk to MySQL
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME  # our settings


def run_query(sql, values=(), fetch=False):
    """Open a connection, run ONE sql command, close the connection."""
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )
    cursor = conn.cursor()
    cursor.execute(sql, values)
    result = None
    if fetch:
        result = cursor.fetchall()      # SELECT: return all rows
    else:
        conn.commit()                   # INSERT / UPDATE: save the change
        result = cursor.lastrowid       # and return the id of the new row
    cursor.close()
    conn.close()
    return result


def create_tables():
    """Create every table the first time the app runs."""
    # one row per chat. Deleting a chat means flipping is_deleted here
    run_query("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id VARCHAR(36) PRIMARY KEY,
            session_title VARCHAR(100) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted BOOLEAN DEFAULT FALSE
        )
    """)
    # one row per message (user or assistant). transcription is only filled for voice messages
    run_query("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id INT AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(36) NOT NULL,
            message TEXT NOT NULL,
            role VARCHAR(10) NOT NULL,
            transcription TEXT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # one row per assistant answer: which model wrote it and the user's like / dislike
    run_query("""
        CREATE TABLE IF NOT EXISTS assistant_messages (
            message_id INT PRIMARY KEY,
            session_id VARCHAR(36) NOT NULL,
            model VARCHAR(50) NOT NULL,
            feedback VARCHAR(10) NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # one row per user message: which switches and file types were used
    run_query("""
        CREATE TABLE IF NOT EXISTS sender_params (
            param_id INT AUTO_INCREMENT PRIMARY KEY,
            message_id INT NOT NULL,
            is_thinking BOOLEAN DEFAULT FALSE,
            is_streaming BOOLEAN DEFAULT FALSE,
            is_searching BOOLEAN DEFAULT FALSE,
            is_voice BOOLEAN DEFAULT FALSE,
            is_image BOOLEAN DEFAULT FALSE,
            is_pdf BOOLEAN DEFAULT FALSE
        )
    """)
    run_query("""
        CREATE TABLE IF NOT EXISTS token_usage (
            usage_id INT AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(36) NOT NULL,
            message_id INT NOT NULL,
            input_tokens INT DEFAULT 0,
            cached_tokens INT DEFAULT 0,
            output_tokens INT DEFAULT 0,
            thinking_tokens INT DEFAULT 0
        )
    """)
    run_query("""
        CREATE TABLE IF NOT EXISTS attachments (
            attachment_id INT AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(36) NOT NULL,
            message_id INT NOT NULL,
            file_name VARCHAR(255) NOT NULL,
            mime_type VARCHAR(100) NOT NULL,
            file_path VARCHAR(500) NOT NULL
        )
    """)


def create_session(session_id, title):
    """NEW: add a chat to the sessions table (called when its first message is sent)."""
    run_query(
        "INSERT INTO sessions (session_id, session_title) VALUES (%s, %s)",
        (session_id, title),
    )


def list_sessions():
    """Get (session_id, title) for every chat that is not deleted, newest first."""
    return run_query(
        "SELECT session_id, session_title FROM sessions "
        "WHERE is_deleted = 0 ORDER BY created_at DESC",
        fetch=True,
    )


def delete_session(session_id):
    """SOFT delete: one row changes, nothing is removed."""
    run_query("UPDATE sessions SET is_deleted = 1 WHERE session_id = %s", (session_id,))


def save_message(session_id, message, role):
    """Insert one chat message and return its message_id."""
    return run_query(
        "INSERT INTO messages (session_id, message, role) VALUES (%s, %s, %s)",
        (session_id, message, role),
    )


def save_transcription(message_id, transcription):
    """NEW: store the text of a voice memo on its message."""
    run_query(
        "UPDATE messages SET transcription = %s WHERE message_id = %s",
        (transcription, message_id),
    )


def load_messages(session_id):
    """Get (message_id, role, message, transcription, feedback) for a chat, oldest first.
    LEFT JOIN adds the like / dislike of assistant messages (empty for user messages)."""
    return run_query(
        "SELECT m.message_id, m.role, m.message, m.transcription, a.feedback "
        "FROM messages m "
        "LEFT JOIN assistant_messages a ON a.message_id = m.message_id "
        "WHERE m.session_id = %s ORDER BY m.message_id",
        (session_id,),
        fetch=True,
    )


def save_assistant_message(message_id, session_id, model):
    """NEW: record which model wrote an answer."""
    run_query(
        "INSERT INTO assistant_messages (message_id, session_id, model) VALUES (%s, %s, %s)",
        (message_id, session_id, model),
    )


def save_feedback(message_id, feedback):
    """NEW: store 'like', 'dislike' or None (NULL) for an assistant message."""
    run_query(
        "UPDATE assistant_messages SET feedback = %s WHERE message_id = %s",
        (feedback, message_id),
    )


def save_sender_params(message_id, is_thinking, is_streaming, is_searching, is_voice, is_image, is_pdf):
    """NEW: record the switches and file types of one user message."""
    run_query(
        "INSERT INTO sender_params "
        "(message_id, is_thinking, is_streaming, is_searching, is_voice, is_image, is_pdf) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (message_id, is_thinking, is_streaming, is_searching, is_voice, is_image, is_pdf),
    )


def save_attachment(session_id, message_id, file_name, mime_type, file_path):
    """Remember that a file belongs to a message. The file itself is on disk."""
    run_query(
        "INSERT INTO attachments (session_id, message_id, file_name, mime_type, file_path) "
        "VALUES (%s, %s, %s, %s, %s)",
        (session_id, message_id, file_name, mime_type, file_path),
    )


def load_attachments(session_id):
    """Get (message_id, file_name, mime_type, file_path) for every file of a chat."""
    return run_query(
        "SELECT message_id, file_name, mime_type, file_path FROM attachments "
        "WHERE session_id = %s ORDER BY attachment_id",
        (session_id,),
        fetch=True,
    )


def save_usage(session_id, message_id, input_tokens, cached_tokens, output_tokens, thinking_tokens):
    """Store the token counts of one Gemini call."""
    run_query(
        "INSERT INTO token_usage "
        "(session_id, message_id, input_tokens, cached_tokens, output_tokens, thinking_tokens) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (session_id, message_id, input_tokens, cached_tokens, output_tokens, thinking_tokens),
    )


def get_usage_totals(session_id):
    """Add up every token type for one chat. Returns 4 numbers."""
    rows = run_query(
        "SELECT SUM(input_tokens), SUM(cached_tokens), SUM(output_tokens), SUM(thinking_tokens) "
        "FROM token_usage WHERE session_id = %s",
        (session_id,),
        fetch=True,
    )
    row = rows[0]
    return [int(x or 0) for x in row]