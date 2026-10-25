# db.py - every function that talks to MySQL lives here

import mysql.connector  # the package that lets Python talk to MySQL
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME  # our settings


def run_query(sql, values=(), fetch=False):
    """Open a connection, run ONE sql command, close the connection."""
    conn = mysql.connector.connect(            # 1. connect to MySQL
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )
    cursor = conn.cursor()                     # 2. a cursor is what runs sql commands
    cursor.execute(sql, values)                # 3. run the command (%s are filled by values safely)
    result = None                              # default: nothing to return
    if fetch:                                  # 4. if we asked for rows (SELECT)...
        result = cursor.fetchall()             #    ...get them all as a list
    else:                                      #    otherwise (INSERT / UPDATE / CREATE)...
        conn.commit()                          #    ...save the change permanently
        result = cursor.lastrowid              #    ...and return the id of the new row
    cursor.close()                             # 5. clean up
    conn.close()
    return result


def create_tables():
    """Create the two tables the first time the app runs."""
    run_query("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id INT AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(36) NOT NULL,
            message TEXT NOT NULL,
            role VARCHAR(10) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted BOOLEAN DEFAULT FALSE
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


def save_message(session_id, message, role):
    """Insert one chat message and return its message_id."""
    return run_query(
        "INSERT INTO messages (session_id, message, role) VALUES (%s, %s, %s)",
        (session_id, message, role),
    )


def load_messages(session_id):
    """Get (role, message) for every message of a session, oldest first."""
    return run_query(
        "SELECT role, message FROM messages "
        "WHERE session_id = %s AND is_deleted = 0 ORDER BY message_id",
        (session_id,),
        fetch=True,
    )


def list_sessions():
    """Get (session_id, title) for every non-deleted session, newest first.
    The title is the first 30 characters of the session's first message."""
    return run_query(
        "SELECT session_id, SUBSTRING(message, 1, 30) FROM messages "
        "WHERE message_id IN ("
        "    SELECT MIN(message_id) FROM messages WHERE is_deleted = 0 GROUP BY session_id"
        ") ORDER BY message_id DESC",
        fetch=True,
    )


def delete_session(session_id):
    """SOFT delete: the rows stay in MySQL, we only flip is_deleted to 1."""
    run_query("UPDATE messages SET is_deleted = 1 WHERE session_id = %s", (session_id,))


def save_usage(session_id, message_id, input_tokens, cached_tokens, output_tokens, thinking_tokens):
    """Store the token counts of one bot answer."""
    run_query(
        "INSERT INTO token_usage "
        "(session_id, message_id, input_tokens, cached_tokens, output_tokens, thinking_tokens) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (session_id, message_id, input_tokens, cached_tokens, output_tokens, thinking_tokens),
    )


def get_usage_totals(session_id):
    """Add up every token type for one session. Returns 4 numbers."""
    rows = run_query(
        "SELECT SUM(input_tokens), SUM(cached_tokens), SUM(output_tokens), SUM(thinking_tokens) "
        "FROM token_usage WHERE session_id = %s",
        (session_id,),
        fetch=True,
    )
    row = rows[0]                                  # SUM always returns exactly one row
    return [int(x or 0) for x in row]              # SUM gives None when empty, so turn None into 0
