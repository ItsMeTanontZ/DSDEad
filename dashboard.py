import streamlit as st
import pandas as pd
import altair as alt
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from config import DB_URL
from models import Location, Party, Candidate, ElectionStatistic, Voted

# Page Configuration
st.set_page_config(page_title="Election Data Insight Dashboard", layout="wide")

# Database Connection
@st.cache_resource
def get_engine():
    return create_engine(DB_URL)

def get_session():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()

# Data Loading Functions
@st.cache_data
def get_unique_values(field_name, current_filters):
    session = get_session()
    query = session.query(getattr(Location, field_name)).distinct()
    
    for key, values in current_filters.items():
        if values:
            query = query.filter(getattr(Location, key).in_(values))
            
    results = [r[0] for r in query.all()]
    session.close()
    return sorted([str(r) for r in results])

@st.cache_data
def get_dashboard_data(filters, election_type_filter):
    session = get_session()
    
    # Helper to apply location filters
    def apply_location_filters(query, model=Location):
        for key, values in filters.items():
            if values:
                query = query.filter(getattr(model, key).in_(values))
        return query

    # Base query for statistics
    stats_query = session.query(
        func.sum(ElectionStatistic.total_voters).label("total_voters"),
        func.sum(ElectionStatistic.voters_turnout).label("voters_turnout"),
        func.sum(ElectionStatistic.valid_ballots).label("valid_ballots"),
        func.sum(ElectionStatistic.invalid_ballots).label("invalid_ballots"),
        func.sum(ElectionStatistic.blank_ballots).label("blank_ballots")
    ).join(Location, ElectionStatistic.location_key == Location.lid)
    
    stats_query = apply_location_filters(stats_query)
    stats_query = stats_query.filter(ElectionStatistic.type == election_type_filter)
    stats = stats_query.first()

    # Vote breakdown
    if election_type_filter == "แบบบัญชีรายชื่อ":
        votes_query = session.query(
            Party.name.label("Party"),
            func.sum(Voted.votes_received).label("Votes")
        ).join(Party, Voted.party_key == Party.pid)
        group_by_cols = ["Party"]
    else:
        votes_query = session.query(
            Candidate.name.label("Candidate"),
            Party.name.label("Party"),
            func.sum(Voted.votes_received).label("Votes")
        ).join(Candidate, Voted.candidate_key == Candidate.cid)\
         .join(Party, Candidate.party_number == Party.pid)
        group_by_cols = ["Candidate", "Party"]

    votes_query = votes_query.join(Location, Voted.location_key == Location.lid)
    votes_query = apply_location_filters(votes_query)
    votes_query = votes_query.filter(Voted.election_type == election_type_filter)
    votes_query = votes_query.group_by(*group_by_cols).order_by(func.sum(Voted.votes_received).desc())
    
    votes_df = pd.DataFrame(votes_query.all())
    
    session.close()
    return stats, votes_df

# UI Layout
st.title("🗳️ Election Data Insight Dashboard")

# Sidebar Filters
st.sidebar.header("Filters")

selected_filters = {}

# Cascading Filters
years = get_unique_values("year", {})
selected_filters["year"] = st.sidebar.multiselect("Year", years)

provinces = get_unique_values("province", {"year": selected_filters["year"]})
selected_filters["province"] = st.sidebar.multiselect("Province", provinces)

areas = get_unique_values("area", {
    "year": selected_filters["year"], 
    "province": selected_filters["province"]
})
selected_filters["area"] = st.sidebar.multiselect("Area (Constituency)", areas)

districts = get_unique_values("district", {
    "year": selected_filters["year"], 
    "province": selected_filters["province"],
    "area": selected_filters["area"]
})
selected_filters["district"] = st.sidebar.multiselect("District (Amphoe)", districts)

subdistricts = get_unique_values("subdistrict", {
    "year": selected_filters["year"], 
    "province": selected_filters["province"],
    "area": selected_filters["area"],
    "district": selected_filters["district"]
})
selected_filters["subdistrict"] = st.sidebar.multiselect("Subdistrict (Tambon)", subdistricts)

units = get_unique_values("unit", {
    "year": selected_filters["year"], 
    "province": selected_filters["province"],
    "area": selected_filters["area"],
    "district": selected_filters["district"],
    "subdistrict": selected_filters["subdistrict"]
})
selected_filters["unit"] = st.sidebar.multiselect("Unit (Polling Station)", units)

election_type = st.sidebar.selectbox("Election Type", ["แบบแบ่งเขต", "แบบบัญชีรายชื่อ"])

# Fetch Data
stats, votes_df = get_dashboard_data(selected_filters, election_type)

if stats and stats.total_voters:
    # Row 1: Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_voters = stats.total_voters or 0
    voters_turnout = stats.voters_turnout or 0
    valid_ballots = stats.valid_ballots or 0
    invalid_ballots = stats.invalid_ballots or 0
    blank_ballots = stats.blank_ballots or 0

    turnout_rate = (voters_turnout / total_voters) * 100 if total_voters > 0 else 0
    valid_rate = (valid_ballots / voters_turnout) * 100 if voters_turnout > 0 else 0
    invalid_rate = (invalid_ballots / voters_turnout) * 100 if voters_turnout > 0 else 0
    
    col1.metric("Total Voters", f"{total_voters:,}")
    col2.metric("Turnout Rate", f"{turnout_rate:.2f}%")
    col3.metric("Valid Ballots", f"{valid_rate:.2f}%")
    col4.metric("Invalid Ballots", f"{invalid_rate:.2f}%")

    # Row 2: Top 10 Chart
    st.divider()
    st.subheader(f"Top 10 {'Parties' if election_type == 'แบบบัญชีรายชื่อ' else 'Candidates'}")
    if not votes_df.empty:
        chart_label = "Party" if election_type == "แบบบัญชีรายชื่อ" else "Candidate"
        top_10 = votes_df.head(10).copy()
        
        # Altair chart for better label control
        chart = alt.Chart(top_10).mark_bar().encode(
            y=alt.Y(f"{chart_label}:N", sort="-x", title=chart_label),
            x=alt.X("Votes:Q", title="Votes Received"),
            tooltip=[chart_label, "Votes"]
        ).properties(
            height=300,  # Fixed height to keep it "thin"
            width="container"
        ).configure_axis(
            labelLimit=500  # Increase label limit to prevent truncation
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No voting data available for this selection.")

    # Row 3: Ballot Distribution Chart
    st.divider()
    st.subheader("Ballot Distribution")
    ballot_data = pd.DataFrame({
        "Type": ["Valid", "Invalid", "Blank"],
        "Count": [valid_ballots, invalid_ballots, blank_ballots]
    })
    
    ballot_chart = alt.Chart(ballot_data).mark_bar().encode(
        y=alt.Y("Type:N", title="Ballot Type"),
        x=alt.X("Count:Q", title="Count"),
        tooltip=["Type", "Count"]
    ).properties(
        height=150,
        width="container"
    )
    st.altair_chart(ballot_chart, use_container_width=True)

    # Row 4: Detailed Data
    st.divider()
    st.subheader("Leaderboard")
    if not votes_df.empty:
        votes_df_display = votes_df.copy()
        votes_df_display.index = range(1, len(votes_df_display) + 1)
        st.dataframe(votes_df_display, use_container_width=True)
    else:
        st.info("No detailed data available.")

else:
    st.warning("No data found for the selected filters. Please check if the database is seeded or try different filters.")

# Footer
st.sidebar.markdown("---")
st.sidebar.info("Data sourced from election database.")
