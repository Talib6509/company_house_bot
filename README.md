# Company house bot
A chat bot build on data from company house uk

A retrieval-based QA system with history and cache feature using:
- LangGraph (workflow orchestration)
- IBM Watsonx (LLM)
- Upstash Vector DB (semantic cache )
- PostgreSQL (history)
- Streamlit (UI)

## Features Overview

### 1. Company Data Retrieval---(data.py)
- Fetches company details from Companies House API
- Extracts structured profile:
  - Overview (name, status, incorporation date)
  - Address
  - Financials (accounts)
  - Compliance (confirmation statements)
  - Risk flags (charges, insolvency)
- Filing history is fetched and structured
- Only last **5 years of filings** are used

### 2. LLM (Strict Retrieval QA)---(app.py)
- Uses IBM Watsonx (`mistral-medium`)
- Works in **strict retrieval mode**
- Rules:
  - Only answers from context
  - No hallucination allowed
  - If data missing → returns:
    ```
    Company data does not have this information
    ```
- Handles:
  - Director changes (AP01, TM01, CH01)
  - Accounts, filings, confirmations
  - Time-based queries (e.g. last 3 years)
 
## ⚡ Cache (Vector DB)---(vdb.py)

### How it works
- Uses **semantic similarity search**
- Question → embedding → vector search
- If similar question found → return cached answer
- Cache HIT → skips LLM + retrieval
- Cache MISS → full pipeline executes

### Key Details
- Cache is **namespaced by company_number**
- Same question across different companies → treated separately
- Same question across different user_id → treated similar
- Uses cosine similarity

### Cache Logic
- Embedding model: `all-mpnet-base-v2`
- Similarity threshold: **0.95**
- Top K results checked: **5**

## History (PostgreSQL)---(historydb.py)

### How it works
- Stores each interaction:
- user_id
- company_number
- question
- answer
- timestamp

### Retrieval
- Fetches last **N messages (default = 10)**
- Ordered by latest → then reversed for conversation flow

### Filtering
### Filtering
- History is filtered by:
  - `user_id`
  - `company_number`

### Key Details
- History is **scoped per (user_id + company_number)** combination
- This ensures strict isolation between:
  - Different users
  - Different companies

- If a user logs in again with a **different company_number**:
  - Previous company history is **NOT loaded**
  - Only history related to the **new company** is used

- If the same user comes back with the **same company_number**:
  - Previous conversation history is **retrieved and reused**

## How to Run
### 1. Clone Repository

    git clone <your-repo-url>
    cd <repo-folder>

---

### 2. Create Virtual Environment

    python -m venv venv
    source venv/bin/activate     
---

### 3. Install Dependencies

    pip install -r requirements.txt

---

### 4. Setup Environment Variables

Create `.env` file:

    API_KEY=your_company_house_api_key
    ibm_key=your_ibm_api_key
    project_id=your_project_id
    gemini_key=your_gemini_key
    UPSTASH_VECTOR_REST_URL=your_url
    UPSTASH_VECTOR_REST_TOKEN=your_token
    SUPABASE_DB_URL=your_db_connection_string

---

### 5. Setup Database

    CREATE TABLE IF NOT EXISTS history (
        id SERIAL PRIMARY KEY,
        user_id TEXT,
        company_number TEXT,
        question TEXT,
        answer TEXT,
        created_at TIMESTAMP
    );

---

### 6. Run Application

    streamlit run streamapp.py

---

### 7. Usage Flow

1. Enter company number  
2. Enter user ID  
3. Ask questions  

---


