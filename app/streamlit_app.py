import streamlit as st
import os
import shutil
import time
import uuid
import threading
from datetime import datetime
from pathlib import Path
import plotly.io as pio

# Set Page Config
st.set_page_config(
    page_title="Sustally — AI Sustainability Intelligence",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    .stChatMessage {
        border-radius: 12px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

# Import backend elements with hot reload support
import importlib
import config.settings
importlib.reload(config.settings)
from config import settings
from src.retrieval.query_classifier import QueryClassifier
from src.retrieval.company_router import CompanyRouter
from src.agents.qa_agent import QAAgent
from src.agents.analysis_agent import AnalysisAgent
from src.agents.comparison_agent import ComparisonAgent
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
def get_metrics_store():
    return MetricsStore()

@st.cache_resource
def get_query_cache():
    return QueryCache()

@st.cache_resource
def get_history_store():
    return HistoryStore()

# Initialize resources
classifier = get_query_classifier()
router = get_company_router()
qa_agent = get_qa_agent()
analysis_agent = get_analysis_agent()
comp_agent = get_comparison_agent()
metrics_store = get_metrics_store()
query_cache = get_query_cache()
history_store = get_history_store()

# Async message persistence helper
def save_message_async(conv_id: int, role: str, content: str, lane: str = None, chart_id: int = None):
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
            "content": m["content"]
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
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state["session_id"] = str(uuid.uuid4())
        st.session_state["active_conversation_id"] = None
        st.session_state["messages"] = []
        st.rerun()
        
    st.markdown("#### 💬 Past Chats")
    conversations = history_store.get_conversations_list()
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
    companies_list_sidebar = router.get_known_companies()
    if companies_list_sidebar:
        for c in companies_list_sidebar:
            years = metrics_store.get_company_years(c)
            st.write(f"• {c} ({', '.join(years) if years else 'No data'})")
    else:
        st.caption("No companies registered yet.")

# 2. MAIN PANEL — CENTERED LAYOUT
left_spacer, main_col, right_spacer = st.columns([1, 3, 1])

with main_col:
    # Header row (Branding on left, engine status badge on right)
    col_left, col_right = st.columns([3, 1])
    with col_left:
        st.markdown("<h2 style='margin-bottom:0px; margin-top:0px;'>🌱 Sustally</h2><p style='color:#888; font-size:14px; margin-top:0px; margin-bottom:15px;'>AI Sustainability Intelligence</p>", unsafe_allow_html=True)
    with col_right:
        last_prov = st.session_state["last_provider"]
        badge_html = ""
        if "omniroute" in last_prov.lower():
            badge_html = "<span style='background-color:#1E4620; color:#3CD070; padding:6px 12px; border-radius:12px; font-weight:bold; font-size:14px; display:inline-block;'>🟢 Engine: OmniRoute</span>"
        elif "ollama" in last_prov.lower():
            badge_html = "<span style='background-color:#1B365D; color:#4E91F2; padding:6px 12px; border-radius:12px; font-weight:bold; font-size:14px; display:inline-block;'>🔵 Engine: Ollama</span>"
        elif "unavailable" in last_prov.lower():
            badge_html = "<span style='background-color:#5C1D1D; color:#F25C5C; padding:6px 12px; border-radius:12px; font-weight:bold; font-size:14px; display:inline-block;'>🔴 Engine: Unavailable</span>"
        else:
            badge_html = f"<span style='background-color:#4A4A4A; color:#E0E0E0; padding:6px 12px; border-radius:12px; font-weight:bold; font-size:14px; display:inline-block;'>🟡 Engine: {last_prov}</span>"
        st.markdown(f"<div style='text-align:right; margin-top:10px;'>{badge_html}</div>", unsafe_allow_html=True)

    st.markdown("Analyze corporate ESG reports, compare metrics, and generate charts instantly.")
    st.markdown("---")

    # Welcome placeholder if conversation is empty
    if not st.session_state["messages"]:
        st.info("👋 **Welcome to Sustally ESG Intelligence Portal!**\n\nAsk a question about greenhouse emissions, compare metrics between TCS and Infosys, or request a narrative report summary to get started.")

    # Display chat messages
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "chart" in msg and msg["chart"] is not None:
                st.plotly_chart(msg["chart"], use_container_width=True)
                if msg.get("chart_reused"):
                    st.caption(f"ℹ️ Showing previously generated chart — refreshed {msg.get('chart_refreshed_time')}")

    # File Uploader Expander
    with st.expander("📤 Ingest New Sustainability Report (PDF/XML)", expanded=False):
        uploaded_file = st.file_uploader("Choose report file", type=["pdf", "xml"], label_visibility="collapsed")
        if uploaded_file:
            st.write("##### Associate metadata:")
            company_input = st.text_input("Company Name (e.g. Infosys Limited)").strip()
            year_input = st.text_input("Report Year (e.g. 2024)").strip()
            
            if st.button("Process & Ingest"):
                if not company_input or not year_input:
                    st.error("Please provide both Company Name and Year.")
                else:
                    target_dir = Path(settings.RAW_DIR) / company_input / year_input
                    target_dir.mkdir(parents=True, exist_ok=True)
                    target_path = target_dir / uploaded_file.name
                    
                    with open(target_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                        
                    with st.spinner("Ingesting report asynchronously..."):
                        manager = DocumentManager()
                        result = manager.ingest_new_reports()
                        st.success(f"Successfully processed: {result['message']}")
                        st.rerun()

    # User Query input (rendered within main column)
    query = st.chat_input("Ask a question, compare companies, or request a report summary...")

    if query:
        # Show user message
        with st.chat_message("user"):
            st.markdown(query)
        
        # Resolve or create conversation
        # Resolve or create conversation
        if st.session_state["active_conversation_id"] is not None:
            conv_id = st.session_state["active_conversation_id"]
        else:
            is_first_msg = (len(st.session_state["messages"]) == 0)
            if is_first_msg:
                conv_title = query
                if len(conv_title) > 60:
                    conv_title = conv_title[:57] + "..."
                conv_id = history_store.create_conversation(st.session_state["session_id"], conv_title)
            else:
                conv_id = history_store.get_conversation_by_session(st.session_state["session_id"])
                if conv_id is None:
                    conv_id = history_store.create_conversation(st.session_state["session_id"], "New Conversation")
            st.session_state["active_conversation_id"] = conv_id
                
        st.session_state["messages"].append({"role": "user", "content": query})
        save_message_async(conv_id, "user", query)
        
        # Query Classification & Routing
        classification = classifier.classify(query)
        lane = classification["lane"]
        comps = classification["companies"]
        years = classification["years"]
        metric_key = classification["metric_key"]
        
        # Handle missing company warning
        if classification["status"] == "missing_company":
            response = "Which company would you like me to analyze? Please specify the company name (e.g. TCS, Infosys)."
            with st.chat_message("assistant"):
                st.markdown(response)
            st.session_state["messages"].append({"role": "assistant", "content": response})
            save_message_async(conv_id, "assistant", response, lane=None)
        else:
            # Check cache
            cache_comp = comps[0] if comps else "all"
            cache_yr = years[0] if years else "latest"
            cached_val = query_cache.get_cached_answer(cache_comp, cache_yr, query)
            
            if cached_val:
                with st.chat_message("assistant"):
                    st.caption("⚡ Response served from Cache (0ms)")
                    st.markdown(cached_val)
                st.session_state["messages"].append({"role": "assistant", "content": cached_val})
                save_message_async(conv_id, "assistant", cached_val, lane=lane)
            else:
                with st.chat_message("assistant"):
                    message_placeholder = st.empty()
                    chart_placeholder = st.empty()
                    
                    full_response = ""
                    fig = None
                    is_reused = False
                    refreshed_time = None
                    chart_id = None
                    
                    # Execute Lane
                    if lane == "A":
                        if metric_key == "list_companies":
                            companies_list = router.get_known_companies()
                            if companies_list:
                                full_response = "Here are the registered companies in Sustally database:\n" + "\n".join([f"- {c}" for c in companies_list])
                            else:
                                full_response = "No companies registered in the database yet. Please upload reports via the sidebar."
                            message_placeholder.markdown(full_response)
                            provider_name = "direct_lookup"
                        else:
                            st.caption("Lane A: Structured Lookup (DB)")
                            t_start = time.time()
                            target_comp = comps[0]
                            target_year = years[0] if years else None
                            
                            import requests
                            try:
                                gen, provider_name, _ = qa_agent.run_lane_a(target_comp, target_year, metric_key, query, stream=True)
                                for token in gen:
                                    full_response += token
                                    message_placeholder.markdown(full_response + "▌")
                            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                                full_response = "⚠️ Connection to LLM failed. Please ensure the backend services are running."
                                provider_name = "unavailable"
                                
                            t_end = time.time()
                            full_response += f"\n\n*(Query completed in {t_end - t_start:.2f}s using {provider_name})*"
                            message_placeholder.markdown(full_response)
                            st.session_state["last_provider"] = provider_name
                            
                    elif lane == "C":
                        st.caption("Lane C: Comparison Engine (Structured + Visual)")
                        t_start = time.time()
                        
                        chart_metric = metric_key if metric_key else "scope1_emissions_tco2e"
                        
                        # Pull comparison structured data and Plotly chart from ComparisonAgent
                        structured_data, gen, provider_name, fig, is_reused, refreshed_time, chart_id = comp_agent.compare_companies(
                            companies=comps,
                            years=years,
                            metric_keys=None,
                            stream=True,
                            chart_metric=chart_metric
                        )
                        
                        if fig:
                            chart_placeholder.plotly_chart(fig, use_container_width=True)
                            if is_reused:
                                st.caption(f"ℹ️ Showing previously generated chart — refreshed {refreshed_time}")
                            
                        import requests
                        try:
                            for token in gen:
                                full_response += token
                                message_placeholder.markdown(full_response + "▌")
                        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                            full_response = "⚠️ Connection to LLM failed. Please ensure the backend services are running."
                            provider_name = "unavailable"
                            
                        t_end = time.time()
                        full_response += f"\n\n*(Query completed in {t_end - t_start:.2f}s using {provider_name})*"
                        message_placeholder.markdown(full_response)
                        st.session_state["last_provider"] = provider_name
                        
                    else:
                        st.caption("Lane B: Narrative RAG")
                        t_start = time.time()
                        target_comp = comps[0]
                        target_year = years[0] if years else None
                        
                        if any(w in query.lower() for w in ["summarize", "summary", "overview"]):
                            gen, provider_name = analysis_agent.summarize_report(target_comp, target_year, stream=True)
                        else:
                            gen, provider_name, _ = qa_agent.run_lane_b(target_comp, target_year, query, stream=True)
                            
                        import requests
                        try:
                            for token in gen:
                                full_response += token
                                message_placeholder.markdown(full_response + "▌")
                        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                            full_response = "⚠️ Connection to LLM failed. Please ensure the backend services are running."
                            provider_name = "unavailable"
                            
                        t_end = time.time()
                        full_response += f"\n\n*(Query completed in {t_end - t_start:.2f}s using {provider_name})*"
                        message_placeholder.markdown(full_response)
                        st.session_state["last_provider"] = provider_name
                    
                    # Save response to cache
                    query_cache.set_cached_answer(cache_comp, cache_yr, query, full_response)
                    
                    # Save message to session state
                    st.session_state["messages"].append({
                        "role": "assistant",
                        "content": full_response,
                        "chart": fig,
                        "chart_reused": is_reused,
                        "chart_refreshed_time": refreshed_time
                    })
                    save_message_async(conv_id, "assistant", full_response, lane=lane, chart_id=chart_id)
                    st.rerun()
