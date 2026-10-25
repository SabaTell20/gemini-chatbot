# pages/Pricing.py - shows token counts and cost for the current session

from datetime import date            # to know which price list is active today
import streamlit as st
import db

# Streamlit forgets toggle values when you leave a page, so we "touch" them to keep them
for key in ["use_search", "use_thinking", "use_streaming"]:
    if key in st.session_state:
        st.session_state[key] = st.session_state[key]

# Prices in USD per 1,000,000 tokens (from the Gemini pricing page)
PRICES_NOW = {"input": 2.00, "cached": 0.10, "output": 10.00}      # until Nov 30, 2026
PRICES_LATER = {"input": 4.00, "cached": 0.20, "output": 20.00}    # from Dec 1, 2026

if date.today() >= date(2026, 12, 1):    # pick the right price list for today's date
    prices = PRICES_LATER
else:
    prices = PRICES_NOW

st.title("💰 Token usage and cost")
st.page_link("app.py", label="⬅ Back to chat")

session_id = st.session_state.get("session_id")      # the chat currently open
if session_id is None:
    st.info("Open a chat first.")
    st.stop()                                        # stop drawing the page here

input_tokens, cached_tokens, output_tokens, thinking_tokens = db.get_usage_totals(session_id)

# Each row: (name, token count, price per 1M tokens). Thinking is billed at the output price.
rows = [
    ("Input (not cached)", input_tokens, prices["input"]),
    ("Cached input", cached_tokens, prices["cached"]),
    ("Output", output_tokens, prices["output"]),
    ("Thinking", thinking_tokens, prices["output"]),
]

table = []                                           # the table we will display
total_cost = 0                                       # running total
for name, tokens, price in rows:
    cost = tokens / 1_000_000 * price                # tokens / 1M * price per 1M
    total_cost += cost
    table.append({
        "Token type": name,
        "Tokens": tokens,
        "Price per 1M": f"${price:.2f}",
        "Cost": f"${cost:.6f}",
    })

table.append({"Token type": "TOTAL", "Tokens": sum(r[1] for r in rows),
              "Price per 1M": "", "Cost": f"${total_cost:.6f}"})

st.caption(f"Session: {session_id}")
st.table(table)                                      # draw the table
