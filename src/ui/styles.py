"""Modern, polished CSS styling for Streamlit UI."""

CHATGPT_CUSTOM_CSS = """
<style>
/* ============================================================
   Modern Professional Design System
   ============================================================ */

/* Hide unwanted Streamlit branding clutter */
#MainMenu, footer, .stDeployButton {
    display: none !important;
}

/* Header & Toolbar: keep clean and accessible */
header[data-testid="stHeader"] {
    background: transparent !important;
}

[data-testid="stToolbar"] {
    display: flex !important;
    visibility: visible !important;
    background: transparent !important;
}

/* Sidebar Toggle Controls */
[data-testid="stExpandSidebarButton"],
button[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapseButton"] button {
    display: inline-flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    background-color: var(--secondary-background-color) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 8px !important;
    padding: 6px 10px !important;
    transition: all 0.2s ease !important;
}

/* Hero Section Container */
.hero-wrapper {
    max-width: 760px;
    margin: 2.5rem auto 1.5rem auto;
    text-align: center;
    padding: 2.5rem 1.5rem 2rem 1.5rem;
    border-radius: 16px;
    background: linear-gradient(180deg, rgba(59, 130, 246, 0.05) 0%, rgba(0, 0, 0, 0) 100%);
    border: 1px solid rgba(255, 255, 255, 0.07);
}

.hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 4px 12px;
    border-radius: 9999px;
    background-color: rgba(59, 130, 246, 0.12);
    color: #60a5fa;
    border: 1px solid rgba(59, 130, 246, 0.25);
    margin-bottom: 1rem;
}

.hero-title {
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.25;
    margin-bottom: 0.75rem;
}

.hero-subtitle {
    font-size: 15px;
    line-height: 1.6;
    color: var(--text-color);
    opacity: 0.75;
    max-width: 580px;
    margin: 0 auto;
}

/* Prompt Suggestion Cards */
.suggestion-header {
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    opacity: 0.6;
    margin: 1.5rem 0 0.75rem 0;
    text-align: center;
}

/* Citation Badges (Pills) */
.citation-container {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin-top: 12px;
    margin-bottom: 8px;
}

.citation-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: 20px;
    background-color: rgba(59, 130, 246, 0.08);
    border: 1px solid rgba(59, 130, 246, 0.24);
    color: #60a5fa !important;
    font-size: 13px;
    font-weight: 500;
    text-decoration: none !important;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.citation-badge:hover {
    background-color: rgba(59, 130, 246, 0.16);
    border-color: rgba(59, 130, 246, 0.45);
    color: #93c5fd !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
}

/* Chat Input Bar (Subtle Modern Rounded) */
[data-testid="stChatInput"] {
    max-width: 820px !important;
    margin: 0 auto !important;
    padding-bottom: 1rem !important;
}

[data-testid="stChatInput"] > div {
    border-radius: 24px !important;
    border: 1px solid var(--border-color) !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12) !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}

[data-testid="stChatInput"] > div:focus-within {
    border-color: var(--primary-color) !important;
    box-shadow: 0 4px 24px rgba(59, 130, 246, 0.2) !important;
}

/* File items in sidebar */
.file-item-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    background-color: var(--secondary-background-color);
    margin-bottom: 6px;
    font-size: 13px;
}

.file-item-title {
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.file-item-size {
    font-size: 11px;
    opacity: 0.6;
    margin-left: 6px;
}

/* Evidence Card Styling */
.evidence-card {
    padding: 10px 14px;
    border-radius: 8px;
    background-color: rgba(255, 255, 255, 0.02);
    border-left: 3px solid #3b82f6;
    margin-bottom: 10px;
}
</style>
"""
