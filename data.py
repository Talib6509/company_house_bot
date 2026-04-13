
from fastapi import FastAPI
import requests, os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict
import json

import warnings
warnings.filterwarnings("ignore")


#config
load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = "https://api.company-information.service.gov.uk"


FILING_TYPE_MAP = {
    # ---- Accounts ----
    "AA": "Accounts filing",

    # ---- Confirmation ----
    "CS01": "Confirmation statement",

    # ---- Directors ----
    "AP01": "Director appointment",
    "TM01": "Director termination",
    "CH01": "Director details change",

    # ---- Secretaries ----
    "AP03": "Secretary appointment",
    "TM02": "Secretary termination",
    "CH03": "Secretary details change",
    "CH04": "Corporate secretary change",

    # ---- Charges ----
    "MR01": "Charge creation",
    "MR02": "Charge satisfaction",
    "MR04": "Charge statement update",

    # ---- Incorporation ----
    "IN01": "Company incorporation",
    "MA": "Memorandum & Articles",

    # ---- Address ----
    "AD01": "Registered office address change",

    # ---- PSC (Ownership) ----
    "PSC01": "PSC notification",
    "PSC02": "PSC update",
    "PSC03": "PSC ceased",

    # ---- Misc ----
    "SH01": "Share allotment",
    "SH02": "Share consolidation",
}


# first api call to fetch company details
def get_company_details(company_number):
    url = f"{BASE_URL}/company/{company_number}"
    response = requests.get(url, auth=(API_KEY, ""))
    if response.status_code == 200:
        data = response.json()
        print(f"Company details: {data}")
        return data
    else:
        print("[ERROR]", response.status_code, response.text)
        return None

def extract_company_profile(details):
    profile = {}

    name = details.get("company_name", "Unknown")
    number = details.get("company_number", "N/A")
    status = details.get("company_status", "Unknown")
    company_type = details.get("type", "N/A")
    jurisdiction = details.get("jurisdiction", "N/A")
    incorporation_date = details.get("date_of_creation", "N/A")
    date_of_cessation = details.get('date_of_cessation', 'N/A')

    # Address
    address_data = details.get("registered_office_address", {})
    address = ", ".join([v for v in address_data.values() if v]) if address_data else "N/A"

    # Accounts
    accounts = details.get("accounts", {})
    last_accounts = accounts.get("last_accounts", {})
    next_accounts = accounts.get("next_accounts", {})

    last_accounts_summary = None
    if last_accounts:
        last_accounts_summary = (
            f"Last accounts ({last_accounts.get('type', 'unknown')}): "
            f"{last_accounts.get('period_start_on', 'N/A')} → {last_accounts.get('period_end_on', 'N/A')}"
        )

    next_accounts_summary = None
    if next_accounts:
        next_accounts_summary = (
            f"Next accounts due on {next_accounts.get('due_on', 'N/A')} "
            f"(Overdue: {next_accounts.get('overdue', False)})"
        )

    # Confirmation statement
    confirmation = details.get("confirmation_statement", {})
    confirmation_summary = None
    if confirmation:
        confirmation_summary = (
            f"Confirmation statement due on {confirmation.get('next_due', 'N/A')} "
            f"(Overdue: {confirmation.get('overdue', False)})"
        )

    # Compliance
    has_charges = details.get("has_charges", False)
    has_insolvency = details.get("has_insolvency_history", False)


    # SIC Codes (business activity)
    sic_codes = details.get("sic_codes", [])
    sic_summary = ", ".join(sic_codes) if sic_codes else "N/A"

    # Previous names
    prev_names = details.get("previous_company_names", [])


    can_file= details.get("can_file", False)

    # Final structured profile
    profile["overview"] = (
        f"{name} (Company No: {number}) is a {company_type.upper()} company "
        f"registered/jurisdiction in {jurisdiction}. Incorporated on {incorporation_date}, "
        f"its current status is '{status}'."
    )

    profile["address"] = f"Registered office: {address}"

    profile["financials"] = {
        "last_accounts": last_accounts_summary,
        "next_accounts": next_accounts_summary,
    }

    profile["compliance"] = {
        "confirmation_statement": confirmation_summary,
        "accounts_overdue": accounts.get("overdue", False),
    }

    profile["risk_flags"] = {
        "has_charges": has_charges,
        "has_insolvency_history": has_insolvency
    }

    profile["business_activity"] = f"SIC Codes: {sic_summary}"

    
    if prev_names:
        formatted_names = {}

        for item in prev_names:
            name = item.get("name")
            start = item.get("effective_from")
            end = item.get("ceased_on")

            if not name:
                continue

            if start and end:
                formatted_names[name] = f"from {start} to {end}"
            elif start and not end:
                formatted_names[name] = f"from {start} to present"
            else:
                formatted_names[name] = "date unknown"
        
        profile["previous_names"] = formatted_names
       
    if date_of_cessation != "N/A":
        profile["dissolution"] = (
            f"Company dissolved on {details.get('date_of_cessation', 'N/A')}"
        )

    if can_file:
        profile["filing_status"] = "Company is eligible to file accounts and confirmation statements."

    return profile



# -------------------------------
# 2. Fetch Filing History
# -------------------------------
def interpret_filing_structured(item):
    type_code = item.get("type")
    category = item.get("category")
    desc = item.get("description", "")
    values = item.get("description_values", {})
    date = item.get("date")
    action_date = item.get("action_date")

    event = {
        "event_type": "unknown",
        "category": category,
        "date": date,
        "action_date": action_date,
        "details": {},
        "raw_type": type_code
    }

    # -------------------------
    # Accounts
    # -------------------------
    if type_code == "AA":
        event["event_type"] = "accounts_filed"

        if "full" in desc:
            event["details"]["accounts_type"] = "full"
        elif "small" in desc:
            event["details"]["accounts_type"] = "small"
        else:
            event["details"]["accounts_type"] = "unknown"

        event["details"]["made_up_to"] = values.get("made_up_date")

    # -------------------------
    # Confirmation Statement
    # -------------------------
    elif type_code == "CS01":
        event["event_type"] = "confirmation_statement_filed"
        event["details"]["made_up_to"] = values.get("made_up_date")

    # -------------------------
    # Director Appointment
    # -------------------------
    elif type_code == "AP01":
        event["event_type"] = "director_appointment"
        event["details"] = {
            "officer_name": values.get("officer_name"),
            "appointment_date": values.get("appointment_date")
        }

    # -------------------------
    # Director Termination
    # -------------------------
    elif type_code == "TM01":
        event["event_type"] = "director_termination"
        event["details"] = {
            "officer_name": values.get("officer_name"),
            "termination_date": values.get("termination_date")
        }

    # -------------------------
    # Director Change
    # -------------------------
    elif type_code == "CH01":
        event["event_type"] = "director_change"
        event["details"] = {
            "officer_name": values.get("officer_name"),
            "change_date": values.get("change_date")
        }

    # -------------------------
    # Address Change
    # -------------------------
    elif type_code == "AD01":
        event["event_type"] = "address_change"

    # -------------------------
    # Charge Creation
    # -------------------------
    elif type_code == "MR01":
        event["event_type"] = "charge_created"

    # -------------------------
    # Charge Satisfaction
    # -------------------------
    elif type_code == "MR02":
        event["event_type"] = "charge_satisfied"

    # -------------------------
    # Fallback
    # -------------------------
    else:
        event["event_type"] = "other"
        event["details"]["description"] = desc

    return event


def get_filing_history(company_number):
    url = f"{BASE_URL}/company/{company_number}/filing-history"
    print(f"\n[STEP 2] Fetching filing history for {company_number}...")

    response = requests.get(url, auth=(API_KEY, ""))

    if response.status_code != 200:
        print("[ERROR]", response.status_code, response.text)
        return None

    data = response.json()
    items = data.get("items", [])

    structured_events = []

    for item in items:  # take recent 20
        structured_events.append(interpret_filing_structured(item))

    return {
        "total_filings": data.get("total_count"),
        "events": structured_events
    }


# -------------------------------
# 3. Filter Last 5 Years
# -------------------------------
def filter_last_5_years(filing_data):
    print("\n[STEP 3] Filtering last 5 years of filings...")

    cutoff = datetime.now() - timedelta(days=5*365)
    filings = filing_data.get("events", [])

    filtered = [
        f for f in filings
        if f.get("date") and datetime.strptime(f["date"], "%Y-%m-%d") >= cutoff
    ]

    # -------------------------
    # Dynamic Grouping
    # -------------------------
    grouped = defaultdict(list)

    for f in filtered:
        event_type = f.get("event_type", "unknown")

        grouped[event_type].append({
            "date": f.get("date"),
            "action_date": f.get("action_date"),
            "details": f.get("details"),
            "raw_type": f.get("raw_type")
        })

    # -------------------------
    # Build Final Output
    # -------------------------
    result = {
        "Total filings in previous five years": len(filtered),
        "filings_by_type": {}
    }

    for event_type, items in grouped.items():
        result["filings_by_type"][event_type] = {
            "total": len(items),
            "details": items
        }

    print(f"[SUCCESS] {len(filtered)} filings in last 5 years\n")
    return {
    "summary": result,
    "events": filtered
    }

def build_llm_context(profile, filings):
    print("\n[STEP 6] Building LLM context...")

    # ---- Company Profile ----
    profile_text = "Company Profile:\n"
    for key, value in profile.items():
        if isinstance(value, list):
            value = ", ".join(value)
        profile_text += f"- {key.replace('_',' ').title()}: {value}\n"

    # ---- Filing History ----
    filings_text = "\nFiling History (Last 5 Years):\n"

    # for f in filings:
    #     date = f.get("date", "N/A")
    #     event_type = f.get("event_type", "unknown")
    #     raw_type = f.get("raw_type", "N/A")
    #     details = f.get("details", {})

    #     # Make details readable
    #     if isinstance(details, dict):
    #         details_str = ", ".join(f"{k}: {v}" for k, v in details.items() if v)
    #     else:
    #         details_str = str(details)

    filings_text += json.dumps(filings, indent=2, default=str)

    context = profile_text + filings_text

    print("[SUCCESS] LLM context created\n")
    print(context)

    return context
