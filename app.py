from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests, os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict
import json


from langgraph.graph import StateGraph, END
from typing import TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

from langchain_ibm import WatsonxLLM
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

from vdb import cache
from historydb import history_store
from data import get_company_details, extract_company_profile, get_filing_history, filter_last_5_years, build_llm_context


#config
load_dotenv()

# app = FastAPI()

GEMINI_API_KEY = os.getenv("gemini_key")
IBM_API_KEY = os.getenv("ibm_key")
PROJECT_ID = os.getenv("project_id")


API_KEY = os.getenv("API_KEY")
BASE_URL = "https://api.company-information.service.gov.uk"

# llm = ChatGoogleGenerativeAI(
#     model="gemini-2.5-flash",
#     google_api_key=GEMINI_API_KEY
# )


#mistral-medium-2505
llm = WatsonxLLM(
    model_id="mistral-large-2512",
    url="https://us-south.ml.cloud.ibm.com",
    apikey=IBM_API_KEY,
    project_id=PROJECT_ID,
    params={
        GenParams.MAX_NEW_TOKENS: 3000,
        GenParams.TEMPERATURE: 0,
    },
)


# #Request model
# class QueryRequest(BaseModel):
#     company_number: str
#     question: str
#     session_id: str


#state for graph
class GraphState(TypedDict):
    company_number: str
    question: str
    session_id: str

    history: str
    profile: dict
    filings: dict
    context: str
    prompt: str
    answer: str
    cache_hit: bool
    error:bool


# Helpers
def route(state):
    return "cached" if state.get("cache_hit") else "retrieval"

def route_after_retrieval(state):
    return "error" if state.get("error") else "context"

def safe_context(context: str):
    return context.replace("{", "{{").replace("}", "}}")


def build_prompt(context, question,history):
    prompt_template = PromptTemplate(
    input_variables=["context", "question"],
template=f"""
You are a retrieval-based QA system.

## STRICT INSTRUCTIONS
- You MUST answer ONLY using the provided context.
- Do NOT use prior knowledge or assumptions.
- Do NOT infer or guess missing information.
- If the answer is not explicitly present in the context, return EXACTLY:
  "Company data does not have this information"

## HALLUCINATION CONTROL
- Do not fabricate names, dates, or events.
- Do not summarize beyond what is present.
- Do not generalize.
- Only extract and organize existing data.

## FILING-SPECIFIC INSTRUCTIONS
- If the question is about director changes, you MUST include ALL relevant filings:
  - AP01 (Director appointment)
  - TM01 (Director termination)
  - CH01 (Director details change)
- Include:
  - officer_name
  - relevant date (appointment/termination/change)
  - filed date (if available)

- Similarly, for other filing types:
  - Extract ALL entries of that type from context
  - Include full details (dates, values, type)

## RESPONSE FORMAT (STRICT)
- Return ONLY the answer.
- Do NOT include explanations, headings, or extra text.
- Structure clearly using bullet points if multiple entries exist.

## CONVERSATION HISTORY
{history}

## CONTEXT
{context}

## QUESTION
{question}
"""
)

    prompt = prompt_template.format(
        context=context,
        question=question
    )
    return prompt


# NODES
# 1. MEMORY NODE
def memory_node(state: GraphState):
    print(f"User: {state['session_id']}")

    history = history_store.format(state["session_id"])

    return {**state, "history": history}


#cache node
def cache_node(state: GraphState):
    print("\nChecking cache...\n")

    result = cache.search(
        company=state["company_number"],
        query=state["question"]
    )

    if result:
        print("CACHE HIT\n")
        return {
            **state,
            "answer": result["answer"],
            "cache_hit": True
        }

    print("CACHE MISS\n")
    return {
        **state,
        "cache_hit": False
    }

# 2. RETRIEVAL NODE
def retrieval_node(state: GraphState):
    company_data = get_company_details(state["company_number"])
    if not company_data:
        print("Company not found")
        return {
            **state,
            "answer": "Company number not found",
            "error": True
        }

    profile = extract_company_profile(company_data)

    filing_data = get_filing_history(state["company_number"])
    filings = filter_last_5_years(filing_data) if filing_data else []

    new_state = {**state, "profile": profile, "filings": filings,"error": False}

    # print(f"Retreiver Node:{new_state}")

    return new_state


# 3. CONTEXT NODE
def context_node(state: GraphState):
    summary = state["filings"]["summary"]
    context = build_llm_context(state["profile"], summary)
    return {**state, "context": safe_context(context)}

# 5. LLM NODE
def llm_node(state: GraphState):

    print(f"History given to LLM:\n{state['history']}\n")
    response = llm.invoke(build_prompt(state["context"], state["question"], state["history"]))

    response = response.strip() if isinstance(response, str) else response.content.strip()

    # fro gemini response.content
    print(f"LLM Response: {response}\n")

    cache.add(
        state["company_number"],
        state["question"],
        response
    )

    return {**state, "answer": response}


# 6. MEMORY SAVE NODE

    

def memory_save_node(state: GraphState):
    
    #if comanpany not found 
    if state.get("error"):
        return state

    history_store.add(
        state["session_id"],
        state["question"],
        state["answer"]
    )

    return state


# -----------------------------
# BUILD GRAPH
# -----------------------------
builder = StateGraph(GraphState)

builder.add_node("memory", memory_node)
builder.add_node("cache", cache_node)
builder.add_node("retrieval", retrieval_node)
builder.add_node("context", context_node)
builder.add_node("llm", llm_node)
builder.add_node("save", memory_save_node)

# FLOW
builder.set_entry_point("memory")
builder.add_edge("memory", "cache")

# CONDITIONAL
builder.add_conditional_edges(
    "cache",
    route,
    {
        "cached": "save",
        "retrieval": "retrieval"
    }
)

builder.add_conditional_edges(
    "retrieval",
    route_after_retrieval,
    {
        "error": "save",    
        "context": "context"
    }
)
builder.add_edge("context", "llm")
builder.add_edge("llm", "save")
builder.add_edge("save", END)

graph = builder.compile()


# # FASTAPI ENDPOINT
# # -----------------------------
# @app.post("/ask")
# def ask(req: QueryRequest):
#     try:
#         result = graph.invoke({
#             "company_number": req.company_number,
#             "question": req.question,
#             "session_id": req.session_id
#         })

#         return {"answer": result["answer"]}

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))