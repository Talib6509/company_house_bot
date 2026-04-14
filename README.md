# company_house_bot
A chat bot build on data from company house uk

A retrieval-based QA system with history and cache feature using:
- LangGraph (workflow orchestration)
- IBM Watsonx (LLM)
- Upstash Vector DB (semantic cache)
- PostgreSQL (history)
- Streamlit (UI)

## Features Overview

### 1. Company Data Retrieval
- Fetches company details from Companies House API
- Extracts structured profile:
  - Overview (name, status, incorporation date)
  - Address
  - Financials (accounts)
  - Compliance (confirmation statements)
  - Risk flags (charges, insolvency)
- Filing history is fetched and structured
- Only last **5 years of filings** are used

### 2. LLM (Strict Retrieval QA)
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
 
## ⚡ Cache (Vector DB)

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

## History (PostgreSQL)

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

