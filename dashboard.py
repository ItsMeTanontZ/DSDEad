import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
import os
import base64
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

# Helper for Icons
def get_image_base64(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            data = f.read()
            return "data:image/jpeg;base64," + base64.b64encode(data).decode()
    except:
        return None

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
    
    def apply_location_filters(query, model=Location):
        for key, values in filters.items():
            if values:
                query = query.filter(getattr(model, key).in_(values))
        return query

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

@st.cache_data
def get_map_winners(filters, election_type_filter):
    session = get_session()
    
    # 1. Get Votes by Subdistrict
    if election_type_filter == "แบบบัญชีรายชื่อ":
        query = session.query(
            Location.district,
            Location.subdistrict,
            Party.name.label("Party"),
            func.sum(Voted.votes_received).label("Votes")
        ).join(Party, Voted.party_key == Party.pid)
    else:
        query = session.query(
            Location.district,
            Location.subdistrict,
            Party.name.label("Party"),
            func.sum(Voted.votes_received).label("Votes")
        ).join(Candidate, Voted.candidate_key == Candidate.cid)\
         .join(Party, Candidate.party_number == Party.pid)

    query = query.join(Location, Voted.location_key == Location.lid)
    for key, values in filters.items():
        if values:
            query = query.filter(getattr(Location, key).in_(values))
    
    query = query.filter(Voted.election_type == election_type_filter)
    query = query.group_by(Location.district, Location.subdistrict, Party.name)
    
    results = pd.DataFrame(query.all())
    session.close()

    if results.empty:
        return pd.DataFrame()

    # Normalize names to prevent mismatch
    results['district'] = results['district'].str.strip()
    results['subdistrict'] = results['subdistrict'].str.strip()

    # Find winner per subdistrict
    idx = results.groupby(['district', 'subdistrict'])['Votes'].transform(max) == results['Votes']
    winners = results[idx].drop_duplicates(['district', 'subdistrict'])
    
    try:
        coords_df = pd.read_excel('พิกัดของแต่ละพื้นที่.xlsx')
        coords_df.columns = ['district', 'subdistrict', 'area', 'lat', 'lon']
        coords_df['district'] = coords_df['district'].str.strip()
        coords_df['subdistrict'] = coords_df['subdistrict'].str.strip()
        
        map_df = pd.merge(winners, coords_df, on=['district', 'subdistrict'], how='inner')
        
        # Attach icons
        map_df['icon_data'] = map_df['Party'].apply(lambda x: get_image_base64(f"res/party_pic/{x}.jpg"))
        
        # Filter out those without icons or coordinates
        map_df = map_df.dropna(subset=['lat', 'lon', 'icon_data'])
        return map_df
    except Exception as e:
        return pd.DataFrame()

# UI Layout
st.title("🗳️ Election Data Insight Dashboard")

# Sidebar Filters
st.sidebar.header("Filters")
selected_filters = {}
years = get_unique_values("year", {})
selected_filters["year"] = st.sidebar.multiselect("Year", years)
provinces = get_unique_values("province", {"year": selected_filters["year"]})
selected_filters["province"] = st.sidebar.multiselect("Province", provinces)
areas = get_unique_values("area", {"year": selected_filters["year"], "province": selected_filters["province"]})
selected_filters["area"] = st.sidebar.multiselect("Area (Constituency)", areas)
districts = get_unique_values("district", {"year": selected_filters["year"], "province": selected_filters["province"], "area": selected_filters["area"]})
selected_filters["district"] = st.sidebar.multiselect("District (Amphoe)", districts)
subdistricts = get_unique_values("subdistrict", {"year": selected_filters["year"], "province": selected_filters["province"], "area": selected_filters["area"], "district": selected_filters["district"]})
selected_filters["subdistrict"] = st.sidebar.multiselect("Subdistrict (Tambon)", subdistricts)
units = get_unique_values("unit", {"year": selected_filters["year"], "province": selected_filters["province"], "area": selected_filters["area"], "district": selected_filters["district"], "subdistrict": selected_filters["subdistrict"]})
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
    tab1, tab2 = st.tabs(["แผนที่", "สถิติ"])

    st.divider()
    with tab1: 
        # Row 2: Winner Map
        st.subheader("Geographic Winner Distribution")
        map_data = get_map_winners(selected_filters, election_type)
        
        if not map_data.empty:
            # Define icon mapping for Pydeck
            # We'll create a single icon dictionary since we're passing the URL/Base64 directly
            map_data["icon"] = map_data["icon_data"].apply(lambda x: {
                "url": x,
                "width": 128,
                "height": 128,
                "anchorY": 128
            })

            layer = pdk.Layer(
                "IconLayer",
                map_data,
                get_icon="icon",
                get_size=40,
                get_position=["lon", "lat"],
                pickable=True,
            )
            
            view_state = pdk.ViewState(
                latitude=map_data["lat"].mean(),
                longitude=map_data["lon"].mean(),
                zoom=9,
                pitch=0,
            )
            
            st.pydeck_chart(pdk.Deck(
                layers=[layer],
                initial_view_state=view_state,
                tooltip={"text": "{subdistrict}\nWinner: {Party}\nVotes: {Votes}"}
            ))
            
            # DEBUG: Show first few rows to verify data
            # with st.expander("Debug: Map Data (Internal)"):
            #     st.write(f"Showing {len(map_data)} data points on map.")
            #     st.dataframe(map_data[['district', 'subdistrict', 'Party', 'Votes', 'lat', 'lon']].head())
        else:
            st.info("No map data available. Please select a Province to view the distribution.")
            # Debugging empty map
            with st.expander("Debug: Why is the map empty?"):
                st.write("Checking coordinate file matching...")
                try:
                    coords = pd.read_excel('พิกัดของแต่ละพื้นที่.xlsx')
                    st.write(f"Excel file loaded with {len(coords)} rows.")
                    st.write("First few subdistricts in Excel:", coords.iloc[:, 1].unique()[:5].tolist())
                except Exception as e:
                    st.error(f"Excel load error: {e}")
    with tab2:
        # Row 3: Top 10 Chart
        st.subheader(f"Top 10 Leaders")
        if not votes_df.empty:
            chart_label = "Party" if election_type == "แบบบัญชีรายชื่อ" else "Candidate"
            top_10 = votes_df.head(10).copy()
            chart = alt.Chart(top_10).mark_bar().encode(
                y=alt.Y(f"{chart_label}:N", sort="-x", title=chart_label),
                x=alt.X("Votes:Q", title="Votes Received"),
                tooltip=[chart_label, "Votes"]
            ).properties(height=300, width="container").configure_axis(labelLimit=500)
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No voting data available.")

        # Row 4: Ballot Distribution Chart
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
        ).properties(height=150, width="container")
        st.altair_chart(ballot_chart, use_container_width=True)

    # Row 5: Detailed Data
    st.subheader("Leaderboard")
    if not votes_df.empty:
        votes_df_display = votes_df.copy()
        votes_df_display.index = range(1, len(votes_df_display) + 1)
        st.dataframe(votes_df_display, use_container_width=True)

else:
    st.warning("No data found for the selected filters.")

# Footer
st.sidebar.markdown("---")
st.sidebar.info("Data sourced from election database.")
