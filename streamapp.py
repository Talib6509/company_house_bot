from sentence_transformers import SentenceTransformer
import streamlit as st
from app import graph
from data import get_company_details
import warnings
warnings.filterwarnings("ignore")

# -------------------------------
# HEADER
# -------------------------------
col1, col2 = st.columns([1, 6])
with col1:
    st.image("logo.png", width=80)
with col2:
    st.title("Company House Chat")

# -------------------------------
# SESSION STATE
# -------------------------------
state = st.session_state
state.setdefault("messages", [])
state.setdefault("company_number", None)
state.setdefault("session_id", None)
state.setdefault("company_info", None)

# -------------------------------
# STEP 1: COMPANY NUMBER
# -------------------------------
if not state.company_number:
    st.info("Enter Company Number")
    user_input = st.chat_input("Enter company number...")
    if user_input:
        state.company_number = user_input.strip()
        st.rerun()

# -------------------------------
# STEP 2: USER ID
# -------------------------------
elif not state.session_id:
    st.info("Enter User ID")
    user_input = st.chat_input("Enter user id...")
    if user_input:
        state.session_id = user_input.strip()

        # fetch company details once after both inputs are set
        details = get_company_details(state.company_number)
        if details:
            address_data = details.get("registered_office_address", {})
            address = ", ".join([v for v in address_data.values() if v]) if address_data else "N/A"

            state.company_info = {
                "Company Name":       details.get("company_name", "N/A"),
                "Company Status":     details.get("company_status", "N/A").capitalize(),
                "Date of Creation":   details.get("date_of_creation", "N/A"),
                "Date of cessation" : details.get('date_of_cessation', 'N/A'),
                "Registered Address": address
            }

        st.rerun()

# -------------------------------
# STEP 3: CHAT
# -------------------------------
else:
    st.success(f"Company: {state.company_number} | User: {state.session_id}")

    # Company info table
    if state.company_info:
        st.subheader("Company Overview")
        st.table(state.company_info)
        st.info("💬 Ask me anything about this company!")

    st.divider()

    # Reset buttons
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Reset Company"):
            state.company_number = None
            state.session_id     = None
            state.messages       = []
            state.company_info   = None
            st.rerun()
    with c2:
        if st.button("Clear Chat"):
            state.messages = []
            st.rerun()

    # Chat history
    for msg in state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("Ask a question...")
    if user_input:
        state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.spinner("Thinking..."):
            result = graph.invoke({
                "company_number": state.company_number,
                "question":       user_input,
                "session_id":     state.session_id
            })
            answer    = result["answer"]
            cache_hit = result.get("cache_hit", False)

        if cache_hit:
            st.info("⚡ Answer retrieved from cache")

        state.messages.append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.markdown(answer)
