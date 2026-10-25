\# Gemini Chatbot with Token Cost Tracking



A multi-session chatbot web app built with Python, Streamlit, MySQL and the Gemini API.

Conversations are saved in MySQL, and a second page shows how many tokens each session used and what they cost.



\## Features



\- Multiple chat sessions shown in the sidebar, with a New chat button

\- Soft delete: deleting a chat hides it from the app but keeps the rows in the database (is\_deleted = 1)

\- Google Search toggle: the bot can only use Google Search when this is switched on

\- Thinking toggle: switches the model's thinking level between low (off) and high (on)

\- Streaming toggle: shows the answer piece by piece instead of all at once

\- Token pricing page: a table per session with input, cached input, output and thinking tokens, their price per 1M tokens, and the cost



\## Tech stack



\- Interface: Streamlit

\- AI model: Gemini API (gemini-4-argon) via the google-genai package

\- Database: MySQL via mysql-connector-python



\## Project files



\- app.py: main chat page

\- db.py: all MySQL functions

\- config.example.py: example settings (copy it to config.py)

\- pages/Pricing.py: token and cost table



\## Database



Two tables, created automatically on first run:



\- messages: message\_id, session\_id, message, role, created\_at, is\_deleted

\- token\_usage: token counts for each bot answer, linked to messages by session\_id and message\_id



\## How the cost is calculated



Prices per 1,000,000 tokens (Standard tier, until November 30, 2026):



\- Input (not cached): $2.00

\- Cached input: $0.10

\- Output: $10.00

\- Thinking: $10.00 (billed as output)



From December 1, 2026 the prices double, and Pricing.py switches by date.

Cost = tokens / 1,000,000 x price. Token counts come from the usage\_metadata of each Gemini response.



\## Setup



1\. Install Python and MySQL (with MySQL Workbench).

2\. In MySQL Workbench, run: CREATE DATABASE IF NOT EXISTS chatbot\_db;

3\. Install the packages: pip install streamlit

