import os
from dotenv import load_dotenv
from supabase import create_client, Client
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

supabase = init_supabase()

# Fetch data
res = supabase.table("walkin_table").select("*").execute()
df = pd.DataFrame(res.data)

# Page layout and CSS to left-align content and use full width
st.set_page_config(page_title="Walkin Leads", layout="wide")
st.markdown(
    """
    <style>
      .block-container { max-width: 100% !important; padding-top: 1rem; padding-bottom: 1rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🚶Walkin Leads")

# Date filter controls (applies to aggregates below and preview)
filter_option = st.selectbox(
    "Date filter (based on created_at)", ["MTD", "Today", "Custom Range", "None"], index=0
)

# Determine start/end datetimes (all in UTC)
now_ts = pd.Timestamp.now(tz="UTC")
today_start = pd.Timestamp(date.today()).tz_localize("UTC")
today_end = today_start + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1)
month_start = pd.Timestamp(date.today().replace(day=1)).tz_localize("UTC")

if filter_option == "Today":
    start_dt, end_dt = today_start, today_end
elif filter_option == "MTD":
    start_dt, end_dt = month_start, now_ts
else:
    col_start, col_end = st.columns(2)
    with col_start:
        custom_start = st.date_input("Start date", value=date.today().replace(day=1))
    with col_end:
        custom_end = st.date_input("End date", value=date.today())
    # Normalize to full-day range
    start_dt = pd.Timestamp(custom_start).tz_localize("UTC")
    end_dt = pd.Timestamp(custom_end).tz_localize("UTC") + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1)

# Apply created_at filter
df_filtered = df.copy()
if filter_option != "None":
    if not df.empty and "created_at" in df.columns:
        created_ts = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
        mask = created_ts.between(start_dt, end_dt)
        df_filtered = df.loc[mask].copy()
    else:
        st.warning("created_at column missing; date filter not applied.")

# Build summary table: unique branches and their row counts
if not df_filtered.empty and "branch" in df_filtered.columns:
    unique_branches = (
        pd.Series(sorted(df_filtered["branch"].dropna().astype(str).unique()))
        .rename("branch")
        .to_frame()
    )
    branch_counts = (
        df_filtered["branch"].astype(str).value_counts().rename_axis("branch").reset_index(name="rows")
    )
    
    # Count pending, won, and lost leads per branch
    if "status" in df_filtered.columns:
        pending_counts = (
            df_filtered[df_filtered["status"].astype(str).str.strip().str.lower() == "pending"]
            .groupby("branch")
            .size()
            .rename_axis("branch")
            .reset_index(name="pending")
        )
        won_counts = (
            df_filtered[df_filtered["status"].astype(str).str.strip().str.lower() == "won"]
            .groupby("branch")
            .size()
            .rename_axis("branch")
            .reset_index(name="won")
        )
        lost_counts = (
            df_filtered[df_filtered["status"].astype(str).str.strip().str.lower() == "lost"]
            .groupby("branch")
            .size()
            .rename_axis("branch")
            .reset_index(name="lost")
        )
    else:
        pending_counts = pd.DataFrame({"branch": [], "pending": []})
        won_counts = pd.DataFrame({"branch": [], "won": []})
        lost_counts = pd.DataFrame({"branch": [], "lost": []})

    # Count touched/untouched leads per branch among Pending status
    if "first_call_date" in df_filtered.columns and "status" in df_filtered.columns:
        status_pending_mask = df_filtered["status"].astype(str).str.strip().str.lower() == "pending"
        has_first_call_mask = df_filtered["first_call_date"].notna() & (df_filtered["first_call_date"].astype(str).str.strip() != "")
        touched_mask = status_pending_mask & has_first_call_mask
        untouched_mask = status_pending_mask & ~has_first_call_mask
        touched_counts = (
            df_filtered[touched_mask]
            .groupby("branch")
            .size()
            .rename_axis("branch")
            .reset_index(name="touched")
        )
        untouched_counts = (
            df_filtered[untouched_mask]
            .groupby("branch")
            .size()
            .rename_axis("branch")
            .reset_index(name="untouched")
        )
    else:
        touched_counts = pd.DataFrame({"branch": [], "touched": []})
        untouched_counts = pd.DataFrame({"branch": [], "untouched": []})
    
    branches_table = unique_branches.merge(branch_counts, on="branch", how="left").fillna({"rows": 0})
    branches_table = branches_table.merge(pending_counts, on="branch", how="left").fillna({"pending": 0})
    branches_table = branches_table.merge(touched_counts, on="branch", how="left").fillna({"touched": 0})
    branches_table = branches_table.merge(untouched_counts, on="branch", how="left").fillna({"untouched": 0})
    branches_table = branches_table.merge(won_counts, on="branch", how="left").fillna({"won": 0})
    branches_table = branches_table.merge(lost_counts, on="branch", how="left").fillna({"lost": 0})
    branches_table["rows"] = branches_table["rows"].astype(int)
    branches_table["pending"] = branches_table["pending"].astype(int)
    branches_table["touched"] = branches_table["touched"].astype(int)
    branches_table["untouched"] = branches_table["untouched"].astype(int)
    branches_table["won"] = branches_table["won"].astype(int)
    branches_table["lost"] = branches_table["lost"].astype(int)
else:
    branches_table = pd.DataFrame({"branch": [], "rows": [], "pending": [], "touched": [], "untouched": [], "won": [], "lost": []})

st.subheader("Branch wise lead Count")
# Order columns: branch, leads punched, pending, touched, untouched, won, lost (where available)
desired_order = ["branch", "rows", "pending", "touched", "untouched", "won", "lost"]
columns_in_order = [col for col in desired_order if col in branches_table.columns]
branches_table = branches_table[columns_in_order]
branches_table_display = branches_table.rename(
    columns={
        "rows": "leads punched",
        "pending": "pending leads",
        "touched": "Touched leads",
        "untouched": "untouched leads",
        "won": "Won Leads",
        "lost": "Lost Leads",
    }
)
st.dataframe(branches_table_display, use_container_width=True)

# Toggle to view/hide underlying raw data (respects selected date filter if applied)
show_underlying = st.toggle("View underlying data", value=False)
if show_underlying:
    st.subheader("Walk-in Table")
    st.dataframe(df_filtered, use_container_width=True)