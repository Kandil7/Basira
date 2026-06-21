"""
Basira Dashboard — Streamlit-based internal monitoring UI.

Provides chat interface, agent monitoring, analytics reports,
and document management for internal users.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import streamlit as st
import httpx
import json
from datetime import datetime

# Page config
st.set_page_config(
    page_title="Basira Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# API base URL
API_BASE_URL = "http://localhost:8000/api/v1"

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔍 Basira")
    st.caption("Multi-Agent AI Platform")

    # Navigation
    page = st.radio(
        "Navigation",
        ["💬 Chat", "📊 Analytics", "📄 Documents", "⚙️ Settings"],
        index=0,
    )

    st.divider()

    # System status
    st.subheader("System Status")
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{API_BASE_URL}/health")
            status = resp.json()
            if status.get("status") == "healthy":
                st.success("✅ System Healthy")
            else:
                st.warning("⚠️ System Degraded")

            # Show service status
            services = status.get("services", {})
            for svc, info in services.items():
                if isinstance(info, dict):
                    svc_status = info.get("status", "unknown")
                else:
                    svc_status = info
                icon = "✅" if svc_status in ("connected", "available") else "❌"
                st.text(f"{icon} {svc}: {svc_status}")
    except Exception:
        st.error("❌ API Unavailable")

# ── Chat Page ──────────────────────────────────────────────────────────────
if page == "💬 Chat":
    st.title("💬 Chat with Basira")

    # Session state for chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = None

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("metadata"):
                st.caption(f"Agent: {message['metadata'].get('agent', 'N/A')} | "
                          f"Intent: {message['metadata'].get('intent', 'N/A')} | "
                          f"Time: {message['metadata'].get('processing_time_ms', 0):.0f}ms")

    # Chat input
    if prompt := st.chat_input("اكتب سؤالك هنا... / Type your question here..."):
        # Display user message
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Send to API
        with st.chat_message("assistant"):
            with st.spinner("جاري التفكير... / Thinking..."):
                try:
                    payload = {
                        "query": prompt,
                        "channel": "web",
                        "session_id": st.session_state.session_id,
                    }

                    with httpx.Client(timeout=30) as client:
                        resp = client.post(
                            f"{API_BASE_URL}/chat",
                            json=payload,
                            headers={"X-Internal-Key": "change-me-in-production"},
                        )
                        result = resp.json()

                    response = result.get("response", "No response")
                    st.markdown(response)

                    # Show metadata
                    metadata = {
                        "agent": result.get("agent"),
                        "intent": result.get("intent"),
                        "processing_time_ms": result.get("processing_time_ms", 0),
                    }
                    st.caption(f"Agent: {metadata['agent']} | "
                              f"Intent: {metadata['intent']} | "
                              f"Time: {metadata['processing_time_ms']:.0f}ms")

                    # Update session
                    st.session_state.session_id = result.get("session_id")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response,
                        "metadata": metadata,
                    })

                except Exception as e:
                    st.error(f"Error: {str(e)}")

# ── Analytics Page ─────────────────────────────────────────────────────────
elif page == "📊 Analytics":
    st.title("📊 Analytics Dashboard")

    # Date range selector
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date")
    with col2:
        end_date = st.date_input("End Date")

    # Tabs for different analytics
    tab1, tab2, tab3, tab4 = st.tabs(["Sales Report", "Branch KPIs", "Inventory", "Export Reports"])

    with tab1:
        st.subheader("Daily Sales Report")
        if st.button("Get Report"):
            with st.spinner("Loading..."):
                try:
                    with httpx.Client(timeout=30) as client:
                        resp = client.post(
                            f"{API_BASE_URL}/reports/daily",
                            json={"date": str(start_date)},
                            headers={"X-Internal-Key": "change-me-in-production"},
                        )
                        data = resp.json()

                    st.json(data)

                    # Display summary
                    summary = data.get("summary", {})
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Total Sales", f"{summary.get('total_sales', 0):,.2f} SAR")
                    with col2:
                        st.metric("Total Orders", summary.get("total_orders", 0))

                except Exception as e:
                    st.error(f"Error: {str(e)}")

    with tab2:
        st.subheader("Branch KPIs")
        branch_ids = st.text_input("Branch IDs (comma-separated)", "1,2,3")
        if st.button("Get KPIs"):
            with st.spinner("Loading..."):
                try:
                    ids = [id.strip() for id in branch_ids.split(",")]
                    with httpx.Client(timeout=30) as client:
                        resp = client.post(
                            f"{API_BASE_URL}/kpis/branches",
                            json={
                                "branch_ids": ids,
                                "start_date": str(start_date),
                                "end_date": str(end_date),
                            },
                            headers={"X-Internal-Key": "change-me-in-production"},
                        )
                        data = resp.json()

                    st.json(data)

                except Exception as e:
                    st.error(f"Error: {str(e)}")

    with tab3:
        st.subheader("Inventory Status")
        threshold = st.number_input("Low Stock Threshold", value=10.0)
        if st.button("Check Stock"):
            with st.spinner("Loading..."):
                try:
                    with httpx.Client(timeout=30) as client:
                        resp = client.post(
                            f"{API_BASE_URL}/inventory/low-stock",
                            json={"threshold": threshold},
                            headers={"X-Internal-Key": "change-me-in-production"},
                        )
                        data = resp.json()

                    st.metric("Low Stock Items", data.get("low_stock_count", 0))

                    if data.get("items"):
                        import pandas as pd
                        df = pd.DataFrame(data["items"])
                        st.dataframe(df)

                except Exception as e:
                    st.error(f"Error: {str(e)}")

    with tab4:
        st.subheader("Export Reports")

        export_format = st.selectbox("Export Format", ["PDF", "Excel", "CSV", "JSON"])
        report_title = st.text_input("Report Title", "تقرير المبيعات")

        if st.button("Export Daily Report"):
            with st.spinner("Generating export..."):
                try:
                    with httpx.Client(timeout=30) as client:
                        resp = client.post(
                            f"{API_BASE_URL}/export/daily",
                            json={
                                "date": str(start_date),
                                "format": export_format.lower(),
                            },
                            headers={"X-Internal-Key": "change-me-in-production"},
                        )

                        if resp.status_code == 200:
                            # Download file
                            content_type = resp.headers.get("content-type", "")
                            if "pdf" in content_type:
                                ext = "pdf"
                            elif "spreadsheet" in content_type:
                                ext = "xlsx"
                            elif "csv" in content_type:
                                ext = "csv"
                            else:
                                ext = "json"

                            st.download_button(
                                label=f"Download {export_format}",
                                data=resp.content,
                                file_name=f"report_{start_date}.{ext}",
                                mime=content_type,
                            )
                            st.success("Report generated successfully!")
                        else:
                            st.error(f"Export failed: {resp.status_code}")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

# ── Documents Page ─────────────────────────────────────────────────────────
elif page == "📄 Documents":
    st.title("📄 Document Management")

    tab1, tab2 = st.tabs(["Upload Document", "Search Documents"])

    with tab1:
        st.subheader("Upload Document to RAG")
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=["pdf", "txt", "md", "xlsx", "csv"],
        )
        summary_type = st.selectbox("Summary Type", ["full", "kpi_extraction", "task_generation"])
        language = st.selectbox("Language", ["ar", "en"])

        if uploaded_file and st.button("Upload & Process"):
            with st.spinner("Processing..."):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                    data = {"summary_type": summary_type, "language": language}

                    with httpx.Client(timeout=60) as client:
                        resp = client.post(
                            f"{API_BASE_URL}/internal/summarize",
                            files=files,
                            data=data,
                            headers={"X-Internal-Key": "change-me-in-production"},
                        )
                        result = resp.json()

                    st.success(f"Document processed: {result.get('document_id')}")
                    st.json(result)

                except Exception as e:
                    st.error(f"Error: {str(e)}")

    with tab2:
        st.subheader("Search Documents")
        query = st.text_input("Search Query")
        limit = st.number_input("Max Results", value=5, min_value=1, max_value=20)

        if query and st.button("Search"):
            with st.spinner("Searching..."):
                try:
                    with httpx.Client(timeout=30) as client:
                        resp = client.post(
                            f"{API_BASE_URL}/internal/search",
                            data={"query": query, "limit": limit},
                            headers={"X-Internal-Key": "change-me-in-production"},
                        )
                        data = resp.json()

                    results = data.get("results", [])
                    st.info(f"Found {len(results)} results")

                    for i, r in enumerate(results, 1):
                        with st.expander(f"Result {i} (Score: {r.get('score', 0):.2f})"):
                            st.text(r.get("content", ""))

                except Exception as e:
                    st.error(f"Error: {str(e)}")

# ── Settings Page ──────────────────────────────────────────────────────────
elif page == "⚙️ Settings":
    st.title("⚙️ Settings")

    st.subheader("API Configuration")
    api_url = st.text_input("API Base URL", API_BASE_URL)
    api_key = st.text_input("API Key", type="password")

    if st.button("Test Connection"):
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(
                    f"{api_url}/health",
                    headers={"X-Internal-Key": api_key},
                )
                if resp.status_code == 200:
                    st.success("Connection successful!")
                else:
                    st.error(f"Connection failed: {resp.status_code}")
        except Exception as e:
            st.error(f"Connection failed: {str(e)}")

    st.subheader("About")
    st.markdown("""
    **Basira (بصيرة)** — Multi-Agent AI Platform for Retail & Food

    - **Version**: 1.0.0
    - **Phase**: 3 (Production Ready)
    - **Agents**: 6 (Analytical, CX, Ops, General, Pricing, Supply Chain)
    - **Features**: Export, Escalation, POS Integration, Training Docs
    """)

    # Pilot monitoring section
    st.divider()
    st.subheader("📊 Pilot Monitoring")
    if st.button("Generate Pilot Report"):
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(
                    f"{API_BASE_URL}/health",
                    headers={"X-Internal-Key": "change-me-in-production"},
                )
                if resp.status_code == 200:
                    st.success("✅ System is healthy for pilot")
                    st.json(resp.json())
                else:
                    st.warning("⚠️ System health check failed")
        except Exception as e:
            st.error(f"Connection error: {str(e)}")
