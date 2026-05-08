import os
import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from config import DB_URL
from models import Location, Party, Candidate, ElectionStatistic, Voted

# Constants
DEFAULT_ELECTION_TYPE = "แบบแบ่งเขต"
ELECTION_TYPES = ["แบบแบ่งเขต", "แบบบัญชีรายชื่อ"]

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

@st.cache_data
def load_coordinates():
    """Load subdistrict coordinates from Excel file"""
    file_path = os.path.join(os.path.dirname(__file__), "พิกัดของแต่ละพื้นที่.xlsx")
    df = pd.read_excel(file_path)
    rename_map = {
        "อำเภอ": "district",
        "ตำบล": "subdistrict",
        "เขต": "area",
    }
    df = df.rename(columns={key: value for key, value in rename_map.items() if key in df.columns})
    # Determine source column for subdistrict and district if renamed
    sub_col = "subdistrict" if "subdistrict" in df.columns else (df.columns[0] if len(df.columns) > 0 else None)
    district_col = "district" if "district" in df.columns else None

    # Group by exact subdistrict and district values so only true duplicates are merged
    def choose_label(vals):
        vals = [v for v in vals if pd.notna(v)]
        if not vals:
            return ""
        return vals[0]

    group_cols = [col for col in [sub_col, district_col] if col]
    agg = df.groupby(group_cols).agg({
        "Latitude": "mean",
        "Longitude": "mean",
        "area": (lambda x: choose_label(x)) if "area" in df.columns else (lambda x: "")
    }).reset_index()

    # normalize output column names
    if sub_col and sub_col != "subdistrict":
        agg = agg.rename(columns={sub_col: "subdistrict"})
    if district_col and district_col != "district":
        agg = agg.rename(columns={district_col: "district"})
    # ensure Latitude/Longitude are numeric
    agg["Latitude"] = pd.to_numeric(agg["Latitude"], errors="coerce")
    agg["Longitude"] = pd.to_numeric(agg["Longitude"], errors="coerce")

    return agg

@st.cache_data
def get_subdistrict_stats(filters, election_type_filter):
    """Get election statistics for each subdistrict"""
    session = get_session()
    
    # Query for subdistrict-level statistics
    query = session.query(
        Location.subdistrict,
        func.sum(ElectionStatistic.total_voters).label("total_voters"),
        func.sum(ElectionStatistic.voters_turnout).label("voters_turnout"),
        func.sum(ElectionStatistic.valid_ballots).label("valid_ballots")
    ).join(Location, ElectionStatistic.location_key == Location.lid)
    
    # Apply filters
    for key, values in filters.items():
        if values:
            query = query.filter(getattr(Location, key).in_(values))
    
    query = query.filter(ElectionStatistic.type == election_type_filter)
    query = query.group_by(Location.subdistrict)
    
    result = query.all()
    session.close()
    
    # Convert to dictionary for easy lookup
    stats_dict = {}
    for row in result:
        stats_dict[row[0]] = {
            "total_voters": row[1] or 0,
            "voters_turnout": row[2] or 0,
            "valid_ballots": row[3] or 0
        }
    
    return stats_dict

def normalize_place_name(value):
    return str(value).replace(" ", "").replace("_", "").replace("(", "").replace(")", "").strip().lower()

def create_map(coordinates_df, subdistrict_stats, selected_filters, election_type, radius_size):
    """Create a pydeck scatter plot with filtered subdistrict data colored by area"""
    # Prepare data for map
    plot_data = []
    normalized_subdistrict_stats = {
        normalize_place_name(name): value for name, value in subdistrict_stats.items()
    }
    selected_areas = {str(area) for area in selected_filters.get("area", []) if str(area)}
    selected_districts = {
        normalize_place_name(name) for name in selected_filters.get("district", []) if str(name)
    }
    selected_subdistricts = {
        normalize_place_name(name) for name in selected_filters.get("subdistrict", []) if str(name)
    }
    
    for idx, row in coordinates_df.iterrows():
        subdistrict_name = row["subdistrict"] if "subdistrict" in coordinates_df.columns else row["พื้นที่"]
        district_name = row["district"] if "district" in coordinates_df.columns else row.get("อำเภอ", "")
        area_value = str(row["area"] if "area" in coordinates_df.columns else row.get("เขต", ""))

        if selected_areas and area_value not in selected_areas:
            continue

        if selected_districts and normalize_place_name(district_name) not in selected_districts:
            continue

        if selected_subdistricts and normalize_place_name(subdistrict_name) not in selected_subdistricts:
            continue

        lat = row["Latitude"]
        lon = row["Longitude"]
        
        # Get stats for this subdistrict
        stats = normalized_subdistrict_stats.get(normalize_place_name(subdistrict_name), {
            "total_voters": 0,
            "voters_turnout": 0,
            "valid_ballots": 0
        })
        
        # Calculate turnout rate
        turnout_rate = (stats['voters_turnout'] / stats['total_voters'] * 100) if stats['total_voters'] > 0 else 0
        
        plot_data.append({
            "latitude": lat,
            "longitude": lon,
            "subdistrict": subdistrict_name,
            "district": district_name,
            "area": area_value,
            "turnout_rate": round(turnout_rate, 2),
            "total_voters": stats['total_voters'],
            "voters_turnout": stats['voters_turnout'],
            "valid_ballots": stats['valid_ballots']
        })
    
    plot_df = pd.DataFrame(plot_data)
    if plot_df.empty:
        return None
    
    # Color palette for areas
    color_palette = [
        [0, 102, 255],     # Blue
        [255, 0, 0],       # Red
        [255, 165, 0],     # Orange
        [0, 128, 0],       # Green
        [128, 0, 128],     # Purple
        [255, 192, 203],   # Pink
        [165, 42, 42],     # Brown
        [0, 128, 128],     # Teal
        [255, 215, 0],     # Gold
        [75, 0, 130],      # Indigo
        [240, 128, 128],   # Light Coral
        [0, 128, 64],      # Dark Green
    ]
    
    # Create area to color mapping, keeping area 9 blue when available
    unique_areas = sorted(plot_df["area"].unique(), key=lambda value: int(value) if str(value).isdigit() else str(value))
    area_colors = {}
    if "9" in unique_areas:
        area_colors["9"] = [0, 102, 255]
    if "10" in unique_areas:
        area_colors["10"] = [255, 0, 0]
    remaining_areas = [area for area in unique_areas if area not in area_colors]
    remaining_palette = [color for color in color_palette if color not in area_colors.values()]
    for i, area in enumerate(remaining_areas):
        area_colors[area] = remaining_palette[i % len(remaining_palette)]
    
    # Add color column based on area
    plot_df["color"] = plot_df["area"].apply(lambda a: area_colors[a])
    
    # Create ScatterplotLayer
    layer = pdk.Layer(
        "ScatterplotLayer",
        plot_df,
        get_position=["longitude", "latitude"],
        get_color="color",
        get_radius=radius_size,
        radius_units="pixels",
        opacity=0.65,
        pickable=True,
        auto_highlight=True
    )
    
    # Set initial view state
    view_state = pdk.ViewState(
        longitude=plot_df["longitude"].mean(),
        latitude=plot_df["latitude"].mean(),
        zoom=9,
        pitch=0
    )
    
    # Create and return deck
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={
            "html": "<b>{subdistrict}</b><br/>District: {district}<br/>Area: {area}<br/>Turnout Rate: {turnout_rate}%<br/>Total Voters: {total_voters}<br/>Voters Turnout: {voters_turnout}<br/>Valid Ballots: {valid_ballots}",
            "style": {
                "backgroundColor": "steelblue",
                "color": "white"
            }
        }
    )
    
    return deck

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

election_type = st.sidebar.selectbox("Election Type", ELECTION_TYPES, index=ELECTION_TYPES.index(DEFAULT_ELECTION_TYPE))
dot_radius = st.sidebar.slider("Dot Radius", min_value=5, max_value=50, value=10, step=1)

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
    tab1, tab2 = st.tabs(["แผนที่", "สถิติ"])

    with tab1:
        # Load coordinates and create map
        coordinates_df = load_coordinates()
        subdistrict_stats = get_subdistrict_stats(selected_filters, election_type)
        map_obj = create_map(coordinates_df, subdistrict_stats, selected_filters, election_type, dot_radius)
        st.pydeck_chart(map_obj)

    with tab2:
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
