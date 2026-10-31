"""ChatGPT-inspired dark theme CSS styles for Streamlit."""

CHATGPT_CUSTOM_CSS = """
<style>
/* ============================================================
   ChatGPT Minimalist Dark Theme
   ============================================================ */

/* Root Font & Background */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
}

.stApp {
    background-color: #212121 !important;
    color: #ececec !important;
}

/* Hide Streamlit Clutter */
#MainMenu, header[data-testid="stHeader"], footer {
    visibility: hidden !important;
    height: 0px !important;
}

.stDeployButton, [data-testid="stToolbar"] {
    display: none !important;
}

/* Max Width Main Container (Centered like ChatGPT) */
.block-container {
    max-width: 820px !important;
    padding-top: 3rem !important;
    padding-bottom: 7rem !important;
    margin: 0 auto !important;
}

/* ============================================================
   Sidebar Styling
   ============================================================ */
[data-testid="stSidebar"] {
    background-color: #171717 !important;
    border-right: 1px solid #2f2f2f !important;
}

[data-testid="stSidebar"] h1, 
[data-testid="stSidebar"] h2, 
[data-testid="stSidebar"] h3 {
    color: #f0f0f0 !important;
    font-weight: 600 !important;
}

[data-testid="stSidebar"] p, 
[data-testid="stSidebar"] span, 
[data-testid="stSidebar"] label {
    color: #b4b4b4 !important;
}

/* Sidebar "New Chat" Button */
[data-testid="stSidebar"] button[kind="secondary"],
[data-testid="stSidebar"] .stButton > button {
    border-radius: 20px !important;
    border: 1px solid #3e3e3e !important;
    background-color: #212121 !important;
    color: #f3f3f3 !important;
    font-weight: 500 !important;
    padding: 8px 16px !important;
    transition: all 0.2s ease-in-out !important;
}

[data-testid="stSidebar"] button[kind="secondary"]:hover,
[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #2f2f2f !important;
    border-color: #555555 !important;
    color: #ffffff !important;
}

/* File Uploader Box in Sidebar */
[data-testid="stFileUploader"] {
    background-color: #212121 !important;
    border: 1px dashed #3e3e3e !important;
    border-radius: 12px !important;
    padding: 10px !important;
}

/* ============================================================
   Chat Messages Styling
   ============================================================ */
[data-testid="stChatMessage"] {
    padding: 16px 0 !important;
    border: none !important;
    background-color: transparent !important;
}

/* User Message Bubble */
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background-color: #2f2f2f !important;
    border-radius: 18px !important;
    padding: 12px 18px !important;
    margin-left: auto !important;
    margin-bottom: 12px !important;
    max-width: 85% !important;
    border: 1px solid #383838 !important;
}

div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p {
    color: #f4f4f4 !important;
    margin-bottom: 0 !important;
}

/* Assistant Message Area */
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    background-color: transparent !important;
    margin-right: auto !important;
    width: 100% !important;
    padding-left: 0 !important;
}

div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) p {
    color: #ececec !important;
    line-height: 1.65 !important;
    font-size: 15.5px !important;
}

/* ============================================================
   Bottom Floating Chat Input Bar (Capsule Pill)
   ============================================================ */
[data-testid="stChatInput"] {
    max-width: 800px !important;
    margin: 0 auto !important;
    bottom: 24px !important;
    background: transparent !important;
}

[data-testid="stChatInput"] > div {
    background-color: #2f2f2f !important;
    border: 1px solid #383838 !important;
    border-radius: 28px !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25) !important;
    padding: 4px 8px !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}

[data-testid="stChatInput"] > div:focus-within {
    border-color: #555555 !important;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4) !important;
}

[data-testid="stChatInput"] textarea {
    color: #ececec !important;
    background-color: transparent !important;
    font-size: 15px !important;
}

[data-testid="stChatInput"] textarea::placeholder {
    color: #8e8e8e !important;
}

[data-testid="stChatInput"] button {
    border-radius: 50% !important;
    background-color: #ececec !important;
    color: #212121 !important;
    width: 32px !important;
    height: 32px !important;
    padding: 0 !important;
    transition: transform 0.15s ease !important;
}

[data-testid="stChatInput"] button:hover {
    background-color: #ffffff !important;
    transform: scale(1.05) !important;
}

/* ============================================================
   Citation Chips & Evidence Expander
   ============================================================ */
.citation-container {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;
    margin-bottom: 6px;
}

.citation-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border-radius: 20px;
    background-color: #262626;
    border: 1px solid #383838;
    color: #10a37f !important;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.2s ease;
}

.citation-chip:hover {
    background-color: #2e2e2e;
    border-color: #10a37f;
}

[data-testid="stExpander"] {
    background-color: #1a1a1a !important;
    border: 1px solid #2e2e2e !important;
    border-radius: 12px !important;
    margin-top: 8px !important;
}

[data-testid="stExpander"] summary {
    color: #b4b4b4 !important;
    font-size: 13.5px !important;
}

[data-testid="stExpander"] summary:hover {
    color: #ececec !important;
}

/* ============================================================
   Minimalist Empty State Hero
   ============================================================ */
.gpt-hero-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 55vh;
    text-align: center;
    padding: 20px;
}

.gpt-hero-icon {
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: linear-gradient(135deg, #10a37f 0%, #1a7f64 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 28px;
    margin-bottom: 20px;
    box-shadow: 0 4px 16px rgba(16, 163, 127, 0.25);
}

.gpt-hero-title {
    font-size: 28px;
    font-weight: 600;
    color: #f3f3f3;
    margin-bottom: 8px;
    letter-spacing: -0.5px;
}

.gpt-hero-subtitle {
    font-size: 15px;
    color: #8e8e8e;
    max-width: 520px;
    line-height: 1.5;
    margin: 0 auto;
}
</style>
"""
