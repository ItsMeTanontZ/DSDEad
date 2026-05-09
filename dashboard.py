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
from config import *
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
        print(f"Image not found: {path}")
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
    try:
        query = session.query(getattr(Location, field_name)).distinct()
        for key, values in current_filters.items():
            if values:
                query = query.filter(getattr(Location, key).in_(values))
        results = [r[0] for r in query.all()]
        return sorted([str(r) for r in results])
    except:
        return []
    finally:
        session.close()

@st.cache_data
def get_dashboard_data(filters, election_type_filter):
    session = get_session()
    try:
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
        return stats, votes_df
    finally:
        session.close()

@st.cache_data
def get_map_data(filters, election_type_filter, map_mode):
    session = get_session()
    debug_info = {"stage": "init", "count": 0}
    try:
        # 1. Base query
        if map_mode == "พรรคที่ชนะการโหวต":
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
            debug_info["raw_query_count"] = len(results)
            
            if results.empty: return pd.DataFrame(), debug_info
            
            results['district'] = results['district'].str.strip()
            results['subdistrict'] = results['subdistrict'].str.strip()
            results['Party'] = results['Party'].str.strip()
            results['Votes'] = pd.to_numeric(results['Votes'], errors='coerce').fillna(0)
            
            max_votes = results.groupby(['district', 'subdistrict'])['Votes'].transform('max')
            data_df = results[results['Votes'] == max_votes].drop_duplicates(['district', 'subdistrict'])
            debug_info["พรรคที่ชนะการโหวตs_count"] = len(data_df)
            
        elif map_mode == "เตรียมบัตรเกิน/ขาด":
            query = session.query(
                Location.district,
                Location.subdistrict,
                func.sum(ElectionStatistic.total_voters).label("total_voters"),
                (func.sum(ElectionStatistic.voters_turnout) + func.sum(ElectionStatistic.remaining_ballots)).label("prepared_ballots")
            ).join(Location, ElectionStatistic.location_key == Location.lid)
            for key, values in filters.items():
                if values:
                    query = query.filter(getattr(Location, key).in_(values))
            query = query.filter(ElectionStatistic.type == election_type_filter)
            query = query.group_by(Location.district, Location.subdistrict)

            data_df = pd.DataFrame(query.all())
            debug_info["raw_query_count"] = len(data_df)
            if data_df.empty:
                return pd.DataFrame(), debug_info

            data_df['district'] = data_df['district'].str.strip()
            data_df['subdistrict'] = data_df['subdistrict'].str.strip()
            data_df['total_voters'] = pd.to_numeric(data_df['total_voters'], errors='coerce').fillna(0)
            data_df['prepared_ballots'] = pd.to_numeric(data_df['prepared_ballots'], errors='coerce').fillna(0)
            data_df['Diff'] = data_df['prepared_ballots'] - data_df['total_voters']
            data_df['AbsDiff'] = data_df['Diff'].abs()
            data_df['OutcomeText'] = data_df['Diff'].apply(
                lambda x: f"เกิน {int(x):,}" if x > 0 else (f"ขาด {int(abs(x)):,}" if x < 0 else "พอดี 0")
            )

        else:
            mode_mapping = {
                "ผู้มาใช้สิทธิ์": "voters_turnout",
                "บัตรดี": "valid_ballots",
                "บัตรเสีย": "invalid_ballots",
                "ไม่ลงคะแนน": "blank_ballots"
            }
            col_name = mode_mapping.get(map_mode)
            query = session.query(
                Location.district,
                Location.subdistrict,
                func.sum(getattr(ElectionStatistic, col_name)).label("Value")
            ).join(Location, ElectionStatistic.location_key == Location.lid)
            for key, values in filters.items():
                if values:
                    query = query.filter(getattr(Location, key).in_(values))
            query = query.filter(ElectionStatistic.type == election_type_filter)
            query = query.group_by(Location.district, Location.subdistrict)
            
            data_df = pd.DataFrame(query.all())
            debug_info["raw_query_count"] = len(data_df)
            if data_df.empty: return pd.DataFrame(), debug_info
            
            data_df['Value'] = pd.to_numeric(data_df['Value'], errors='coerce').fillna(0)
            data_df['district'] = data_df['district'].str.strip()
            data_df['subdistrict'] = data_df['subdistrict'].str.strip()

        # 2. Join with Coordinates
        coords_df = pd.read_excel('พิกัดของแต่ละพื้นที่.xlsx')
        coords_df.columns = ['district', 'subdistrict', 'area', 'lat', 'lon']
        coords_df['district'] = coords_df['district'].str.strip()
        coords_df['subdistrict'] = coords_df['subdistrict'].str.strip()
        
        map_df = pd.merge(data_df, coords_df, on=['district', 'subdistrict'], how='inner')
        debug_info["merged_count"] = len(map_df)
        
        if map_mode == "พรรคที่ชนะการโหวต":
            map_df['icon_data'] = map_df['Party'].apply(lambda x: get_image_base64(f"{DATAPIC_DIR}/{x}.jpg"))
            # map_df['icon_path'] = map_df['Party'].apply(lambda x: f"{DATAPIC_DIR}/{x}.jpg")
            # map_df['icon_data'] = map_df['icon_path'].apply(get_image_base64)
            
            missing_icons = map_df[map_df['icon_data'].isna()]['Party'].unique().tolist()
            debug_info["missing_icons"] = missing_icons
            
            map_df = map_df.dropna(subset=['lat', 'lon', 'icon_data'])
            debug_info["final_count"] = len(map_df)
        else:
            map_df = map_df.dropna(subset=['lat', 'lon'])
            debug_info["final_count"] = len(map_df)
            
        return map_df, debug_info
    except Exception as e:
        debug_info["error"] = str(e)
        return pd.DataFrame(), debug_info
    finally:
        session.close()


@st.cache_data
def get_blank_ballots(filters, election_type_filter, group_by_col="unit"):
    session = get_session()
    try:
        # group_by_col should be one of Location fields (unit, subdistrict, district, area)
        if group_by_col not in ["unit", "subdistrict", "district", "area"]:
            group_by_col = "unit"

        query = session.query(
            getattr(Location, group_by_col).label(group_by_col),
            func.sum(ElectionStatistic.blank_ballots).label("Votes")
        ).join(Location, ElectionStatistic.location_key == Location.lid)

        for key, values in filters.items():
            if values:
                query = query.filter(getattr(Location, key).in_(values))

        query = query.filter(ElectionStatistic.type == election_type_filter)
        query = query.group_by(getattr(Location, group_by_col)).order_by(func.sum(ElectionStatistic.blank_ballots).desc())

        df = pd.DataFrame(query.all())
        if df.empty:
            return pd.DataFrame()
        df[group_by_col] = df[group_by_col].astype(str).str.strip()
        df['Votes'] = pd.to_numeric(df['Votes'], errors='coerce').fillna(0)
        return df
    finally:
        session.close()


@st.cache_data
def get_no_show_voters(filters, election_type_filter, group_by_col="unit"):
    session = get_session()
    try:
        # group_by_col should be one of Location fields (unit, subdistrict, district, area)
        if group_by_col not in ["unit", "subdistrict", "district", "area"]:
            group_by_col = "unit"

        query = session.query(
            getattr(Location, group_by_col).label(group_by_col),
            (func.sum(ElectionStatistic.total_voters) - func.sum(ElectionStatistic.voters_turnout)).label("Votes")
        ).join(Location, ElectionStatistic.location_key == Location.lid)

        for key, values in filters.items():
            if values:
                query = query.filter(getattr(Location, key).in_(values))

        query = query.filter(ElectionStatistic.type == election_type_filter)
        query = query.group_by(getattr(Location, group_by_col)).order_by(
            (func.sum(ElectionStatistic.total_voters) - func.sum(ElectionStatistic.voters_turnout)).desc()
        )

        df = pd.DataFrame(query.all())
        if df.empty:
            return pd.DataFrame()
        df[group_by_col] = df[group_by_col].astype(str).str.strip()
        df['Votes'] = pd.to_numeric(df['Votes'], errors='coerce').fillna(0)
        return df
    finally:
        session.close()

# UI Layout
st.title("🗳️ สถิติการเลือกตั้ง")

# Sidebar Filters
st.sidebar.header("ตัวกรอง")
selected_filters = {}
years = get_unique_values("year", {})
selected_filters["year"] = st.sidebar.multiselect("ปี", years, placeholder="เลือก")
provinces = get_unique_values("province", {"year": selected_filters["year"]})
selected_filters["province"] = st.sidebar.multiselect("จังหวัด", provinces, placeholder="เลือก")
areas = get_unique_values("area", {"year": selected_filters["year"], "province": selected_filters["province"]})
selected_filters["area"] = st.sidebar.multiselect("เขตเลือกตั้ง", areas, placeholder="เลือก")
districts = get_unique_values("district", {"year": selected_filters["year"], "province": selected_filters["province"], "area": selected_filters["area"]})
selected_filters["district"] = st.sidebar.multiselect("อำเภอ", districts, placeholder="เลือก")
subdistricts = get_unique_values("subdistrict", {"year": selected_filters["year"], "province": selected_filters["province"], "area": selected_filters["area"], "district": selected_filters["district"]})
selected_filters["subdistrict"] = st.sidebar.multiselect("ตำบล (เทศบาล)", subdistricts, placeholder="เลือก")
units = get_unique_values("unit", {"year": selected_filters["year"], "province": selected_filters["province"], "area": selected_filters["area"], "district": selected_filters["district"], "subdistrict": selected_filters["subdistrict"]})
selected_filters["unit"] = st.sidebar.multiselect("หน่วยเลือกตั้ง", units, placeholder="เลือก")

election_type = st.sidebar.selectbox("รูปแบบการเลือกตั้ง", ["แบบแบ่งเขต", "แบบบัญชีรายชื่อ"])

st.sidebar.markdown("---")
st.sidebar.header("การตั้งค่าแผนที่")
map_mode = st.sidebar.selectbox("รูปแบบแผนที่", ["พรรคที่ชนะการโหวต", "ผู้มาใช้สิทธิ์", "บัตรดี", "บัตรเสีย", "ไม่ลงคะแนน", "เตรียมบัตรเกิน/ขาด"])
dot_scale = st.sidebar.slider("ตัวคูณขนาด", 1, 100, 20)

# Fetch Data
stats, votes_df = get_dashboard_data(selected_filters, election_type)

if stats and stats.total_voters:
    # Row 1: Metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    total_voters = stats.total_voters or 0
    voters_turnout = stats.voters_turnout or 0
    valid_ballots = stats.valid_ballots or 0
    invalid_ballots = stats.invalid_ballots or 0
    blank_ballots = stats.blank_ballots or 0
    turnout_rate = (voters_turnout / total_voters) * 100 if total_voters > 0 else 0
    valid_rate = (valid_ballots / voters_turnout) * 100 if voters_turnout > 0 else 0
    invalid_rate = (invalid_ballots / voters_turnout) * 100 if voters_turnout > 0 else 0
    blank_rate = (blank_ballots / voters_turnout) * 100 if voters_turnout > 0 else 0
    col1.metric("จำนวนคนที่มีสิทธิ์ใช้เสียง", f"{total_voters:,}")
    col2.metric("มาใช้เสียงจริง (%)", f"{turnout_rate:.2f}%", help=f"{voters_turnout} คน จากทั้งหมด {total_voters} คน")
    col3.metric("บัตรดี/ทั้งหมด (%)", f"{valid_rate:.2f}%", help=f"{valid_ballots} ใบ จากทั้งหมด {voters_turnout} ใบ")
    col4.metric("บัตรเสีย/ทั้งหมด (%)", f"{invalid_rate:.2f}%", help=f"{invalid_ballots} ใบ จากทั้งหมด {voters_turnout} ใบ")
    col5.metric("ไม่ลงคะแนน/ทั้งหมด (%)", f"{blank_rate:.2f}%", help=f"{blank_ballots} ใบ จากทั้งหมด {voters_turnout} ใบ")

    # Row 2: Geographic Visualization
    tab1, tab2 = st.tabs(["แผนที่", "สถิติ"])

    with tab1: 
        st.subheader(f"แผนที่แสดงข้อมูล{map_mode}")
        map_data, debug = get_map_data(selected_filters, election_type, map_mode)
        
        if not map_data.empty:
            try:
                if map_mode == "พรรคที่ชนะการโหวต":
                    map_data["icon"] = map_data["icon_data"].apply(lambda x: {
                        "url": x, "width": 128, "height": 128, "anchorY": 128
                    })
                    layer = pdk.Layer(
                        "IconLayer", map_data, 
                        get_icon="icon",
                        get_size=dot_scale, 
                        get_position=["lon", "lat"], 
                        pickable=True,
                    )
                    tooltip_text = "{subdistrict}\nพรรคที่ชนะการโหวต: {Party}\nคะแนน: {Votes}"
                elif map_mode == "เตรียมบัตรเกิน/ขาด":
                    # Normalize radius so all points scale comparably across the current filtered dataset.
                    max_abs_diff = map_data["AbsDiff"].max()
                    if max_abs_diff > 0:
                        map_data["radius"] = ((map_data["AbsDiff"] / max_abs_diff) ** 0.5) * (dot_scale * 120)
                    else:
                        map_data["radius"] = dot_scale * 20
                    map_data["color"] = map_data["Diff"].apply(
                        lambda x: [0, 170, 0, 180] if x > 0 else ([220, 30, 30, 180] if x < 0 else [128, 128, 128, 160])
                    )
                    layer = pdk.Layer(
                        "ScatterplotLayer",
                        map_data,
                        get_position=["lon", "lat"],
                        get_radius="radius",
                        radius_min_pixels=4,
                        radius_max_pixels=60,
                        get_fill_color="color",
                        pickable=True,
                    )
                    tooltip_text = "{subdistrict}\nเตรียมบัตรไว้: {prepared_ballots}\nผู้มีสิทธิ์เลือกตั้ง: {total_voters}\n{OutcomeText} ใบ"
                else:
                    map_data["radius"] = map_data["Value"] * (dot_scale/20)
                    layer = pdk.Layer(
                        "ScatterplotLayer",
                        map_data,
                        get_position=["lon", "lat"],
                        get_radius="radius",
                        radius_min_pixels=3,
                        radius_max_pixels=100,
                        get_fill_color=[255, 0, 0, 160] if map_mode == "บัตรเสีย" else [0, 128, 255, 160],
                        pickable=True,
                    )
                    tooltip_text = "{subdistrict}\n{Value} counts"

                view_state = pdk.ViewState(
                    latitude=map_data["lat"].mean(),
                    longitude=map_data["lon"].mean(),
                    zoom=9, pitch=0,
                )
                
                st.pydeck_chart(pdk.Deck(
                    layers=[layer],
                    initial_view_state=view_state,
                    tooltip={"text": tooltip_text}
                ))
            except Exception as e:
                st.error(f"Error rendering map: {e}")
        else:
            st.info("No map data available. Check the Debug expander below for details.")
        
        # Debug Expander
        # with st.expander("🔍 Map Data Debugger"):
        #     st.write("**Data Pipeline Status:**")
        #     st.json(debug)
        #     if map_mode == "พรรคที่ชนะการโหวต" and "missing_icons" in debug and debug["missing_icons"]:
        #         st.warning(f"Failed to find images for: {', '.join(debug['missing_icons'])}")
        #         st.info(f"Ensure filenames match exactly (including spaces) in `{DATAPIC_DIR}/` with `.jpg` extension.")
    with tab2:
        # Row 3: Top 10 Chart
        if not votes_df.empty:
            chart_label = "Party" if election_type == "แบบบัญชีรายชื่อ" else "Candidate"
            if election_type == "แบบบัญชีรายชื่อ":
                st.subheader(f"10 อันดับพรรคที่คะแนนมากที่สุด")
            else:
                st.subheader(f"10 อันดับ สส ที่คะแนนมากที่สุด")
            top_10 = votes_df.head(10).copy()
            chart = alt.Chart(top_10).mark_bar().encode(
                y=alt.Y(f"{chart_label}:N", sort="-x", title=""),
                x=alt.X("Votes:Q", title="คะแนนที่ได้รับ"),
                tooltip=[chart_label, "Votes"]
            ).properties(height=300, width="container").configure_axis(labelLimit=500)
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No voting data available.")

        # Row 4: Ballot Distribution Chart
        st.divider()
        st.subheader("สถิติการเลือกตั้ง")
        
        col1, col2, col3 = st.columns([3,5,5])
        with col1:
            ballot_data = pd.DataFrame({
                "Type": ["บัตรดี", "บัตรเสีย", "ไม่ลงคะแนน"],
                "Count": [valid_ballots, invalid_ballots, blank_ballots]
            })
            ballot_chart = alt.Chart(ballot_data).mark_arc().encode(
                theta=alt.Theta("Count:Q", title="จำนวน"),
                color=alt.Color("Type:N", title="ประเภทบัตร"),
                tooltip=["Type", "Count"]
            ).properties(height=300, width="container")
            st.altair_chart(ballot_chart, use_container_width=True)
        with col2:
            # If a subdistrict is selected, drill down to unit ranking within that subdistrict.
            group_by = "unit" if selected_filters.get("subdistrict") else ("unit" if selected_filters.get("unit") else "subdistrict")
            subdistrict_label = ", ".join(selected_filters.get("subdistrict", []))
            title_suffix = f"ใน{subdistrict_label}" if subdistrict_label else ""
            blank_df = get_blank_ballots(selected_filters, election_type, group_by)

            if not blank_df.empty:
                # show top 20 areas by blank ballots
                display_df = blank_df.head(10).copy()
                if group_by == "unit":
                    display_df["unit_order"] = pd.to_numeric(
                        display_df[group_by].astype(str).str.extract(r"(\d+)")[0],
                        errors="coerce"
                    ).fillna(0)
                    display_df = display_df.sort_values(["Votes", "unit_order", group_by], ascending=[False, True, True], kind="mergesort")
                    y_sort = display_df[group_by].tolist()
                else:
                    display_df = display_df.sort_values(["Votes", group_by], ascending=[False, True], kind="mergesort")
                    y_sort = "-x"
                chart = alt.Chart(display_df).mark_bar().encode(
                    y=alt.Y(f"{group_by}:N", sort=y_sort, title=""),
                    x=alt.X("Votes:Q", title=f"10 อันดับ{('หน่วย' if group_by == 'unit' else 'ตำบล')}{title_suffix}ที่มีจำนวนบัตรไม่ลงคะแนนมากสุด".replace("  ", " ").strip()),
                    tooltip=[group_by, "Votes"]
                ).properties(height=300, width="container").configure_axis(labelLimit=500)
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("ไม่พบข้อมูลบัตรไม่ลงคะแนนจากที่กรอง")
        with col3:
            # Show non-voters using the same grouped bar style as the blank-ballot breakdown.
            group_by = "unit" if selected_filters.get("subdistrict") else ("unit" if selected_filters.get("unit") else "subdistrict")
            subdistrict_label = ", ".join(selected_filters.get("subdistrict", []))
            title_suffix = f"ใน{subdistrict_label}" if subdistrict_label else ""
            no_show_df = get_no_show_voters(selected_filters, election_type, group_by)

            if not no_show_df.empty:
                display_df = no_show_df.head(10).copy()
                if group_by == "unit":
                    display_df["unit_order"] = pd.to_numeric(
                        display_df[group_by].astype(str).str.extract(r"(\d+)")[0],
                        errors="coerce"
                    ).fillna(0)
                    display_df = display_df.sort_values(["Votes", "unit_order", group_by], ascending=[False, True, True], kind="mergesort")
                    y_sort = display_df[group_by].tolist()
                else:
                    display_df = display_df.sort_values(["Votes", group_by], ascending=[False, True], kind="mergesort")
                    y_sort = "-x"
                chart = alt.Chart(display_df).mark_bar().encode(
                    y=alt.Y(f"{group_by}:N", sort=y_sort, title=""),
                    x=alt.X("Votes:Q", title=f"10 อันดับ{('หน่วย' if group_by == 'unit' else 'ตำบล')}{title_suffix}ที่ผู้ไม่มาใช้สิทธิ์มากสุด".replace("  ", " ").strip()),
                    tooltip=[group_by, "Votes"]
                ).properties(height=300, width="container").configure_axis(labelLimit=500)
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("ไม่พบข้อมูลผู้ไม่มาใช้เสียงจากที่กรอง")

    # Row 5: Detailed Data
    st.divider()
    st.subheader("ตารางแสดงอันดับ")
    if not votes_df.empty:
        votes_df_display = votes_df.copy()
        votes_df_display.index = range(1, len(votes_df_display) + 1)
        st.dataframe(votes_df_display, use_container_width=True)

else:
    st.warning("ไม่ค้นพบข้อมูลจากการกรอง")

# Footer
st.sidebar.markdown("---")
st.sidebar.info("""ชุดข้อมูลนี้ถูกจัดทำขึ้นผ่านกระบวนการ OCR พร้อมการตรวจสอบความถูกต้องแบบ manual เพื่อเพิ่มความแม่นยำก่อนเผยแพร่ ทั้งนี้ เราไม่มีการแก้ไข ดัดแปลง หรือบิดเบือนข้อมูลการเลือกตั้งไม่ว่ากรณีใด ๆ

โครงการนี้เป็น Final Project ของรายวิชา Data Science and Data Engineering รหัสวิชา 2110446 ไม่มีความเกี่ยวข้องกับธุรกิจ พรรคการเมือง หรือองค์กรภาคประชาชนใด ๆ ทั้งสิ้น

สำหรับผลการเลือกตั้งที่เป็นทางการและมีผลอ้างอิงสูงสุด กรุณาอ้างอิงจากเอกสารต้นฉบับของ กกต. เท่านั้น""")
