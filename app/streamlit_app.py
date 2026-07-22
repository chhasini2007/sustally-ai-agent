import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

import streamlit as st
import shutil
import time
import uuid
import threading
from datetime import datetime
from pathlib import Path
import plotly.io as pio
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# Set Page Config
st.set_page_config(
    page_title="Sustally — AI Sustainability Intelligence",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Authentication check
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

@st.dialog("🔒 Sign In / Sign Up")
def login_dialog():
    tab_login, tab_signup = st.tabs(["🔒 Log In", "📝 Sign Up"])
    
    with tab_login:
        username = st.text_input("Username", key="dialog_username", placeholder="Enter username")
        password = st.text_input("Password", type="password", key="dialog_password", placeholder="Enter password")
        submitted = st.button("Sign In", key="dialog_login_submit", use_container_width=True)
        if submitted:
            from src.database.users_store import UsersStore
            users_store = UsersStore()
            expected_user = os.getenv("STREAMLIT_APP_USER")
            expected_pass = os.getenv("STREAMLIT_APP_PASSWORD")
            if not expected_user or not expected_pass:
                expected_user = os.getenv("DEMO_USER", "admin")
                expected_pass = os.getenv("DEMO_PASS", "sustally_secure_demo_pass_2026")
            
            auth_success = False
            if username == expected_user and password == expected_pass:
                auth_success = True
                st.session_state["username"] = expected_user
            elif users_store.authenticate_user(username, password):
                auth_success = True
                st.session_state["username"] = username
                
            if auth_success:
                st.session_state["authenticated"] = True
                st.session_state["auth_just_succeeded"] = True
                st.toast("Access Granted!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Invalid Username or Password.")
    
    with tab_signup:
        new_username = st.text_input("Choose Username", key="dialog_signup_username", placeholder="Choose username")
        new_password = st.text_input("Choose Password", type="password", key="dialog_signup_password", placeholder="Choose password")
        confirm_password = st.text_input("Confirm Password", type="password", key="dialog_signup_confirm_password", placeholder="Confirm password")
        registered = st.button("Register Account", key="dialog_signup_submit", use_container_width=True)
        if registered:
            if not new_username:
                st.error("Username cannot be empty.")
            elif len(new_password) < 8:
                st.error("Password must be at least 8 characters long.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                from src.database.users_store import UsersStore
                users_store = UsersStore()
                success, msg = users_store.create_user(new_username, new_password)
                if success:
                    st.success("Account created successfully! Please switch to Log In tab to access your dashboard.")
                else:
                    st.error(msg)

# Dark Theme CSS injection
st.markdown("""
<style>
    /* Dark Theme Core Adjustments */
    .stApp {
        background-color: #0E1117;
        color: #E0E0E0;
    }
    h1, h2, h3 {
        color: #00E676 !important;
        font-family: 'Outfit', 'Inter', sans-serif;
    }
    
    /* User right-aligned message bubble */
    div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-user"]),
    div[data-testid="stChatMessage"]:has(span[data-testid="stChatMessageAvatar"] img[src*="user"]) {
        background-color: #1b261c !important; /* cute dark sage green */
        border: 1px solid #273829 !important;
        border-radius: 16px 16px 0px 16px !important;
        margin-left: auto !important;
        width: fit-content !important;
        max-width: 80% !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Assistant transparent message container */
    div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-assistant"]),
    div[data-testid="stChatMessage"]:has(span[data-testid="stChatMessageAvatar"] img[src*="assistant"]),
    div[data-testid="stChatMessage"]:has(span[data-testid="stChatMessageAvatar"]):not(:has(img[src*="user"])) {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding-left: 0px !important;
        padding-right: 0px !important;
        margin-right: auto !important;
        width: 100% !important;
    }
    
    /* Animated Sprout Loader styling */
    @keyframes sprout-pulse {
        0% { opacity: 0.4; transform: scale(0.9); }
        50% { opacity: 1; transform: scale(1.2); }
        100% { opacity: 0.4; transform: scale(0.9); }
    }
    .sprout-loader {
        display: inline-block;
        animation: sprout-pulse 1s infinite ease-in-out;
        margin-left: 4px;
        font-size: 1.2em;
    }
</style>
""", unsafe_allow_html=True)

# Import backend elements with hot reload support
import importlib
import config.settings
importlib.reload(config.settings)
from config import settings

import src.retrieval.company_router
importlib.reload(src.retrieval.company_router)
from src.retrieval.company_router import CompanyRouter

import src.retrieval.query_classifier
importlib.reload(src.retrieval.query_classifier)
from src.retrieval.query_classifier import QueryClassifier

# Clear resource cache to ensure reloaded classes are used
st.cache_resource.clear()
from src.agents.qa_agent import QAAgent
from src.agents.analysis_agent import AnalysisAgent
from src.agents.comparison_agent import ComparisonAgent
from src.agents.yoy_agent import YoYAgent
from src.visualization.charts import create_comparison_chart
from src.ingestion.document_manager import DocumentManager
from src.database.metrics_store import MetricsStore
from src.database.history_store import HistoryStore
from src.utils.cache import QueryCache

# Singletons / Cached resources
@st.cache_resource
def get_query_classifier():
    return QueryClassifier()

@st.cache_resource
def get_company_router():
    return CompanyRouter()

@st.cache_resource
def get_qa_agent():
    return QAAgent()

@st.cache_resource
def get_analysis_agent():
    return AnalysisAgent()

@st.cache_resource
def get_comparison_agent():
    return ComparisonAgent()

@st.cache_resource
def get_yoy_agent():
    return YoYAgent()

@st.cache_resource
def get_metrics_store():
    return MetricsStore()

@st.cache_resource
def get_query_cache():
    return QueryCache()

@st.cache_resource
def get_history_store():
    return HistoryStore()

@st.cache_resource
def get_esg_query_engine():
    from src.retrieval.esg_query_engine import ESGQueryEngine
    return ESGQueryEngine()

# Initialize resources
classifier = get_query_classifier()
router = get_company_router()
qa_agent = get_qa_agent()
analysis_agent = get_analysis_agent()
comp_agent = get_comparison_agent()
yoy_agent = get_yoy_agent()
metrics_store = get_metrics_store()
query_cache = get_query_cache()
history_store = get_history_store()

# Async message persistence helper
def save_message_async(conv_id: int, role: str, content: str, lane: str = None, chart_id: int = None):
    if st.session_state.get("username") is None or conv_id is None:
        return
    def _save():
        store = HistoryStore()
        store.add_message(conv_id, role, content, lane, chart_id)
    t = threading.Thread(target=_save)
    t.start()

# Load historical messages helper
def load_conversation_messages(conversation_id: int):
    db_msgs = history_store.get_conversation_messages(conversation_id)
    messages = []
    for m in db_msgs:
        msg = {
            "role": m["role"],
            "content": m["content"],
            "lane": m["lane"]
        }
        if m["figure_json"]:
            try:
                msg["chart"] = pio.from_json(m["figure_json"])
                msg["chart_reused"] = True
                msg["chart_refreshed_time"] = datetime.fromisoformat(m["chart_created_at"]).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                msg["chart"] = None
        messages.append(msg)
    return messages

def save_current_guest_conversation(username: str):
    if not st.session_state.get("messages"):
        return
    
    first_user_msg = "New Conversation"
    for m in st.session_state["messages"]:
        if m["role"] == "user":
            first_user_msg = m["content"]
            break
    conv_title = first_user_msg
    if len(conv_title) > 60:
        conv_title = conv_title[:57] + "..."
        
    conv_id = history_store.create_conversation(st.session_state["session_id"], conv_title, username=username)
    st.session_state["active_conversation_id"] = conv_id
    
    for m in st.session_state["messages"]:
        history_store.add_message(
            conversation_id=conv_id,
            role=m["role"],
            content=m["content"],
            lane=m.get("lane"),
            chart_id=m.get("chart_id")
        )

# Initialize session ID and active conversation ID
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())

if "active_conversation_id" not in st.session_state:
    st.session_state["active_conversation_id"] = None

if "messages" not in st.session_state:
    st.session_state["messages"] = []

if "last_env_provider" not in st.session_state:
    st.session_state["last_env_provider"] = settings.LLM_PROVIDER

if st.session_state["last_env_provider"] != settings.LLM_PROVIDER:
    st.session_state["last_env_provider"] = settings.LLM_PROVIDER
    st.session_state["last_provider"] = settings.LLM_PROVIDER

if "last_provider" not in st.session_state:
    st.session_state["last_provider"] = settings.LLM_PROVIDER

# 1. LEFT SIDEBAR — CHAT HISTORY
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/leaf.png", width=44)
    st.markdown("### Sustally")
    st.caption("AI Sustainability Intelligence")
    st.markdown("---")
    
    # New Chat Button
    if st.button("➕ New Chat", type="primary", use_container_width=True):
        st.session_state["session_id"] = str(uuid.uuid4())
        st.session_state["active_conversation_id"] = None
        st.session_state["messages"] = []
        st.rerun()
        
    # Clear Chat History Button
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        history_store.clear_user_history(st.session_state.get("username"))
        st.session_state["session_id"] = str(uuid.uuid4())
        st.session_state["active_conversation_id"] = None
        st.session_state["messages"] = []
        st.toast("Chat history cleared!")
        time.sleep(1)
        st.rerun()
        
    st.markdown("#### 💬 Past Chats")
    if st.session_state.get("username") is None:
        st.info("🕒 Temporary chat — sign in to save history")
    else:
        conversations = history_store.get_conversations_list(username=st.session_state.get("username"))
        if conversations:
            for c in conversations:
                title = c["title"] or "New Conversation"
                if len(title) > 32:
                    title = title[:29] + "..."
                
                is_current = (c["session_id"] == st.session_state["session_id"])
                
                dt_str = ""
                if c["created_at"]:
                    try:
                        dt_str = datetime.fromisoformat(c["created_at"]).strftime("%b %d, %H:%M")
                    except Exception:
                        pass
                
                # visual indicator for current conversation
                prefix = "👉 " if is_current else "💬 "
                label = f"{prefix}{title}\n({dt_str})" if dt_str else f"{prefix}{title}"
                
                if st.button(label, key=f"conv_{c['id']}", disabled=is_current, use_container_width=True):
                    st.session_state["session_id"] = c["session_id"]
                    st.session_state["active_conversation_id"] = c["id"]
                    st.session_state["messages"] = load_conversation_messages(c["id"])
                    st.rerun()
        else:
            st.caption("No past conversations.")
        
    st.markdown("---")
    
    # Database statistics
    st.markdown("#### 📊 Registered Companies")
    manager = DocumentManager()
    manager.load_index()

    st.markdown("#### 📁 Active Report")
    from pathlib import Path
    registered_files = list(manager.index.keys())
    if registered_files:
        options = ["None Selected"] + registered_files
        def format_file_option(opt):
            if opt == "None Selected":
                return opt
            entry = manager.index[opt]
            comp = entry.get("company", "Unknown")
            year = entry.get("year", "Unknown")
            filename = Path(opt).name
            return f"{comp} - {year} ({filename})"
            
        default_idx = 0
        active_file = st.session_state.get("active_file")
        if active_file in registered_files:
            default_idx = registered_files.index(active_file) + 1
            
        selected_option = st.selectbox(
            "Select active report",
            options=options,
            index=default_idx,
            format_func=format_file_option,
            label_visibility="collapsed"
        )
        
        if selected_option != "None Selected":
            st.session_state["active_file"] = selected_option
            entry = manager.index[selected_option]
            st.session_state["active_company"] = entry.get("company")
            st.session_state["active_year"] = entry.get("year")
        else:
            st.session_state["active_file"] = None
            st.session_state["active_company"] = None
            st.session_state["active_year"] = None
    else:
        st.caption("No reports indexed yet.")
        st.session_state["active_file"] = None
        st.session_state["active_company"] = None
        st.session_state["active_year"] = None
        
    st.markdown("---")
    
    company_tree = {}
    for path, entry in manager.index.items():
        comp = entry.get("company")
        year = entry.get("year")
        ftype = entry.get("file_type", "").upper()
        if not comp or not year:
            continue
            
        display_comp = comp
        for alias, canonical in router.aliases.items():
            if canonical == comp and len(alias) < len(display_comp):
                display_comp = alias.upper()
        
        if display_comp.lower() == "tcs":
            display_comp = "TCS"
        elif display_comp.lower() == "infosys":
            display_comp = "Infosys"
        elif display_comp.lower() == "wipro":
            display_comp = "Wipro"
            
        if display_comp not in company_tree:
            company_tree[display_comp] = {}
        if year not in company_tree[display_comp]:
            company_tree[display_comp][year] = set()
        if ftype:
            company_tree[display_comp][year].add(ftype)
            
    if company_tree:
        for comp, years_dict in sorted(company_tree.items()):
            st.markdown(f"**{comp}**")
            sorted_years = sorted(years_dict.keys())
            for idx, yr in enumerate(sorted_years):
                types_str = " + ".join(sorted(years_dict[yr]))
                connector = "└── " if idx == len(sorted_years) - 1 else "├── "
                st.markdown(f"<span style='font-family:monospace; font-size: 14px;'> &nbsp;{connector}{yr} ({types_str})</span>", unsafe_allow_html=True)
    else:
        st.caption("No companies registered yet.")
        
    if st.session_state.get("username") is not None:
        st.markdown("---")
        if st.button("🔒 Log Out", use_container_width=True):
            st.session_state["authenticated"] = False
            st.session_state["username"] = None
            st.session_state["session_id"] = str(uuid.uuid4())
            st.session_state["active_conversation_id"] = None
            st.session_state["messages"] = []
            st.rerun()

# 2. MAIN PANEL — CENTERED LAYOUT
left_spacer, main_col, right_spacer = st.columns([1, 3, 1])

with main_col:
    col_left, col_middle, col_right = st.columns([4, 2, 1.5])
    with col_left:
        st.markdown("<h2 style='margin-bottom:0px; margin-top:0px;'>🌱 Sustally</h2><p style='color:#888; font-size:14px; margin-top:0px; margin-bottom:15px;'>AI Sustainability Intelligence</p>", unsafe_allow_html=True)
    with col_middle:
        active_prov = qa_agent.llm_router.get_active_provider()
        badge_html = ""
        if "ollama" in active_prov.lower():
            badge_html = "<span style='background-color:#1B365D; color:#4E91F2; padding:6px 12px; border-radius:12px; font-weight:bold; font-size:14px; display:inline-block;'>🔵 Engine: Ollama</span>"
        elif "openai" in active_prov.lower():
            badge_html = "<span style='background-color:#10A37F; color:#FFFFFF; padding:6px 12px; border-radius:12px; font-weight:bold; font-size:14px; display:inline-block;'>🟢 Engine: OpenAI</span>"
        elif "unavailable" in active_prov.lower():
            badge_html = "<span style='background-color:#5C1D1D; color:#F25C5C; padding:6px 12px; border-radius:12px; font-weight:bold; font-size:14px; display:inline-block;'>🔴 Engine: Unavailable</span>"
        else:
            badge_html = f"<span style='background-color:#4A4A4A; color:#E0E0E0; padding:6px 12px; border-radius:12px; font-weight:bold; font-size:14px; display:inline-block;'>🟡 Engine: {active_prov}</span>"
        st.markdown(f"<div style='text-align:right; margin-top:10px;'>{badge_html}</div>", unsafe_allow_html=True)
    with col_right:
        if not st.session_state.get("authenticated"):
            if st.button("🔒 Sign In", key="top_right_signin_btn", use_container_width=True):
                login_dialog()
        else:
            username = st.session_state.get("username")
            st.markdown(f"<div style='text-align:right; margin-top:15px; font-weight:bold; color:#8FBC8F;'>👤 {username}</div>", unsafe_allow_html=True)

    st.markdown("Analyze corporate ESG reports, compare metrics, and generate charts instantly.")
    st.markdown("---")

    # Guest conversation conversion banner
    if st.session_state.get("auth_just_succeeded") and st.session_state.get("messages"):
        with st.container(border=True):
            st.markdown("💬 **Save this temporary guest conversation to your account?**")
            col_save_yes, col_save_no = st.columns([1, 4])
            with col_save_yes:
                if st.button("💾 Yes, Save", use_container_width=True):
                    save_current_guest_conversation(st.session_state["username"])
                    st.session_state["auth_just_succeeded"] = False
                    st.toast("Conversation saved successfully!")
                    st.rerun()
            with col_save_no:
                if st.button("❌ No, Thanks", use_container_width=True):
                    st.session_state["auth_just_succeeded"] = False
                    st.rerun()

    # Welcome placeholder if conversation is empty
    if not st.session_state["messages"]:
        st.write("")
        st.write("")
        st.write("")
        st.write("")
        st.markdown("<h3 style='text-align: center; color: #8FBC8F; font-family: Outfit, Inter, sans-serif;'>🌱 What would you like to know about your sustainability reports?</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #888; font-size: 14px; margin-bottom: 25px;'>Ask a question, compare carbon footprints, or request a report summary.</p>", unsafe_allow_html=True)
        
        # Centered input card
        with st.container(border=True):
            query = st.text_area("Ask Sustally:", placeholder="Ask a question, compare companies, or request a report summary...", key="empty_state_input", height=100, label_visibility="collapsed")
            col_spacer, col_btn = st.columns([5, 1])
            with col_btn:
                submit_clicked = st.button("🚀 Ask", use_container_width=True)
                
            if submit_clicked and query.strip():
                st.session_state["pending_query"] = query.strip()
                st.rerun()
    else:
        # Display chat messages
        for idx, msg in enumerate(st.session_state["messages"]):
            with st.chat_message(msg["role"]):
                if msg.get("lane") in ("G", "GENERAL") and msg["role"] == "assistant":
                    st.markdown("<div style='margin-bottom: 8px;'><span style='background-color: #3e2723; color: #ffb74d; padding: 4px 8px; border-radius: 4px; font-size: 0.85em; font-weight: bold; border: 1px solid #e5a93b;'>⚠️ General knowledge — not from your uploaded reports</span></div>", unsafe_allow_html=True)
                st.markdown(msg["content"])
                if "chart" in msg and msg["chart"] is not None:
                    st.plotly_chart(msg["chart"], use_container_width=True)
                    if msg.get("chart_reused"):
                        st.caption(f"ℹ️ Showing previously generated chart — refreshed {msg.get('chart_refreshed_time')}")
                
                # Copy Response Action under assistant messages
                if msg["role"] == "assistant":
                    copy_text = msg["content"]
                    if st.button("📋 Copy", key=f"copy_btn_{idx}", help="Copy response to clipboard"):
                        import subprocess
                        try:
                            subprocess.run("clip", input=copy_text.encode("utf-16"), check=True)
                            st.toast("Copied response to clipboard!")
                        except Exception as e:
                            st.error(f"Copy failed: {e}")

    # File Uploader Expander
    with st.expander("📤 Ingest New Sustainability Report (PDF/XML)", expanded=False):
        uploaded_files = st.file_uploader("Choose report files", type=["pdf", "xml"], accept_multiple_files=True, label_visibility="collapsed")
        if uploaded_files:
            # Check if there is any PDF file uploaded
            has_pdf = any(f.name.lower().endswith(".pdf") for f in uploaded_files)
            
            company_input = ""
            year_input = ""
            if has_pdf:
                st.write("##### Associate metadata for PDF reports:")
                company_input = st.text_input("Company Name (e.g. Infosys Limited)").strip()
                year_input = st.text_input("Report Year (e.g. 2024)").strip()
                
            if st.button("Process & Ingest"):
                import hashlib
                if has_pdf and (not company_input or not year_input):
                    st.error("Please provide both Company Name and Year for PDF reports.")
                else:
                    newly_placed_files = []
                    processed_xml_count = 0
                    skipped_xml_count = 0
                    errors = []
                    
                    temp_dir = Path("temp_ingest")
                    temp_dir.mkdir(exist_ok=True)
                    
                    manager = DocumentManager()
                    manager.load_index()
                    
                    for uploaded_file in uploaded_files:
                        file_bytes = uploaded_file.getvalue()
                        file_hash = hashlib.sha256(file_bytes).hexdigest()
                        
                        # Check if already indexed
                        is_indexed = False
                        for path, val in manager.index.items():
                            if val.get("file_hash") == file_hash:
                                is_indexed = True
                                break
                                
                        if is_indexed:
                            if uploaded_file.name.lower().endswith(".xml"):
                                skipped_xml_count += 1
                            continue
                            
                        if uploaded_file.name.lower().endswith(".xml"):
                            temp_path = temp_dir / uploaded_file.name
                            with open(temp_path, "wb") as f:
                                f.write(file_bytes)
                                
                            from src.ingestion.bulk_xml_importer import detect_metadata_from_xml, get_unique_filename
                            company, year, error_reason = detect_metadata_from_xml(temp_path)
                            
                            # Clean up temp file
                            if temp_path.exists():
                                os.remove(temp_path)
                                
                            if error_reason:
                                errors.append(f"Could not parse {uploaded_file.name}: {error_reason}")
                                continue
                                
                            st.session_state["active_company"] = company
                            st.session_state["active_year"] = year
                            
                            target_dir = Path(settings.RAW_DIR) / company / year
                            target_dir.mkdir(parents=True, exist_ok=True)
                            target_path = get_unique_filename(target_dir, uploaded_file.name)
                            
                            with open(target_path, "wb") as f:
                                f.write(file_bytes)
                                
                            newly_placed_files.append(str(target_path))
                            processed_xml_count += 1
                        else:
                            # PDF report
                            target_dir = Path(settings.RAW_DIR) / company_input / year_input
                            target_dir.mkdir(parents=True, exist_ok=True)
                            target_path = target_dir / uploaded_file.name
                            
                            with open(target_path, "wb") as f:
                                f.write(file_bytes)
                                
                            newly_placed_files.append(str(target_path))
                            resolved_comps, _ = router.resolve_companies_and_years(company_input)
                            st.session_state["active_company"] = resolved_comps[0] if resolved_comps else company_input
                            st.session_state["active_year"] = year_input
                            
                    # Clean up temp dir if empty
                    if temp_dir.exists():
                        try:
                            temp_dir.rmdir()
                        except Exception:
                            pass
                            
                    if errors:
                        for err in errors:
                            st.error(err)
                            
                    if newly_placed_files:
                        with st.spinner("Ingesting reports asynchronously..."):
                            result = manager.ingest_new_reports(target_files=newly_placed_files)
                            if processed_xml_count > 0:
                                st.success("XML files indexed successfully.")
                            st.success("Report indexed successfully.")
                            time.sleep(2)
                            st.rerun()
                    else:
                        if processed_xml_count == 0 and skipped_xml_count > 0:
                            st.info("Uploaded XML files were already indexed (skipped).")
                            time.sleep(2)
                            st.rerun()
                        elif not errors:
                            st.warning("No files were processed.")

    # Bulk Import Expander
    with st.expander("📁 Bulk Import ESG Reports", expanded=False):
        import_path_str = st.text_input("Root folder path (e.g. ESG_Reports/)", key="bulk_import_folder_path").strip()
        if st.button("Start Bulk Import"):
            if not import_path_str:
                st.error("Please enter a valid folder path.")
            else:
                import_path = Path(import_path_str)
                if not import_path.exists() or not import_path.is_dir():
                    st.error("Provided path does not exist or is not a directory.")
                else:
                    status_container = st.empty()
                    
                    status_container.info("Scanning folders...")
                    time.sleep(0.5)
                    
                    all_scanned_files = []
                    pdf_files = []
                    xml_files = []
                    for root_dir, dirs, files in os.walk(import_path):
                        for f in files:
                            f_path = Path(root_dir) / f
                            all_scanned_files.append(f_path)
                            if f.lower().endswith(".pdf"):
                                pdf_files.append(f_path)
                            elif f.lower().endswith(".xml"):
                                xml_files.append(f_path)
                                
                    status_container.info("Parsing XML...")
                    time.sleep(0.5)
                    
                    status_container.info("Parsing PDF...")
                    time.sleep(0.5)
                    
                    status_container.info("Generating embeddings...")
                    time.sleep(0.5)
                    
                    status_container.info("Updating vector database...")
                    
                    import hashlib
                    from src.ingestion.bulk_xml_importer import detect_metadata_from_xml, detect_metadata_from_pdf
                    
                    newly_placed_files = []
                    indexed_count = 0
                    skipped_count = 0
                    
                    manager = DocumentManager()
                    manager.load_index()
                    
                    for file_path in pdf_files + xml_files:
                        try:
                            with open(file_path, "rb") as f:
                                file_bytes = f.read()
                            file_hash = hashlib.sha256(file_bytes).hexdigest()
                            
                            is_duplicate_hash = False
                            for p_key, val in manager.index.items():
                                if val.get("file_hash") == file_hash:
                                    is_duplicate_hash = True
                                    break
                                    
                            if is_duplicate_hash:
                                skipped_count += 1
                                continue
                                
                            if file_path.suffix.lower() == ".xml":
                                company, year, error_reason = detect_metadata_from_xml(file_path)
                            else:
                                company, year, error_reason = detect_metadata_from_pdf(file_path)
                                
                            if error_reason:
                                continue
                                
                            target_dir = Path(settings.RAW_DIR) / company / year
                            target_path = target_dir / file_path.name
                            target_dir.mkdir(parents=True, exist_ok=True)
                            
                            with open(target_path, "wb") as f:
                                f.write(file_bytes)
                                
                            newly_placed_files.append(str(target_path))
                            indexed_count += 1
                            
                        except Exception as e:
                            pass
                            
                    if newly_placed_files:
                        manager.ingest_new_reports(target_files=newly_placed_files)
                        st.session_state["active_company"] = company
                        st.session_state["active_year"] = year
                        
                    status_container.success("Completed.")
                    time.sleep(1)
                    status_container.empty()
                    
                    st.markdown("### 📊 Import Summary")
                    st.write(f"- **Files scanned**: {len(all_scanned_files)}")
                    st.write(f"- **PDF files**: {len(pdf_files)}")
                    st.write(f"- **XML files**: {len(xml_files)}")
                    st.write(f"- **New reports indexed**: {indexed_count}")
                    st.write(f"- **Duplicates skipped**: {skipped_count}")
                    
                    time.sleep(4)
                    st.rerun()

    # Intercept pending query from centered input, or get from bottom chat input
    query = None
    if "pending_query" in st.session_state and st.session_state["pending_query"]:
        query = st.session_state["pending_query"]
        st.session_state["pending_query"] = None
    elif st.session_state["messages"]:
        query = st.chat_input("Ask a question, compare companies, or request a report summary...")

    if query:
        # Show user message
        with st.chat_message("user"):
            st.markdown(query)
        
        # Resolve or create conversation
        if st.session_state.get("username") is not None:
            if st.session_state["active_conversation_id"] is not None:
                conv_id = st.session_state["active_conversation_id"]
            else:
                is_first_msg = (len(st.session_state["messages"]) == 0)
                if is_first_msg:
                    conv_title = query
                    if len(conv_title) > 60:
                        conv_title = conv_title[:57] + "..."
                    conv_id = history_store.create_conversation(st.session_state["session_id"], conv_title, username=st.session_state.get("username"))
                else:
                    conv_id = history_store.get_conversation_by_session(st.session_state["session_id"])
                    if conv_id is None:
                        conv_id = history_store.create_conversation(st.session_state["session_id"], "New Conversation", username=st.session_state.get("username"))
            st.session_state["active_conversation_id"] = conv_id
        else:
            conv_id = None
                
        st.session_state["messages"].append({"role": "user", "content": query})
        save_message_async(conv_id, "user", query)
        
        # Multi-Agent Pipeline Execution
        esg_engine = get_esg_query_engine()
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            chart_placeholder = st.empty()
            
            with st.spinner("Analyzing disclosures across Multi-Agent ESG Pipeline..."):
                result = esg_engine.process_query(
                    query=query,
                    conversation_context=st.session_state.get("messages", []),
                    active_company=st.session_state.get("active_company")
                )
                
            full_response = result["response_text"]
            fig = result.get("chart")
            
            message_placeholder.markdown(full_response)
            if fig is not None:
                chart_placeholder.plotly_chart(fig, use_container_width=True)
                
        st.session_state["messages"].append({
            "role": "assistant",
            "content": full_response,
            "chart": fig
        })
        save_message_async(conv_id, "assistant", full_response, lane="ESG_AGENT")
        st.rerun()

