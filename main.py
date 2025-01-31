# ~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~
#      /\_/\
#     ( o.o )
#      > ^ <
#
# Author: Johan Hanekom
# Date: January 2025

# ~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~

# =========== // STANDARD IMPORTS // ===========

from urllib.parse import quote

# =========== // CUSTOM IMPORTS // ===========

from streamlit_folium import folium_static
import streamlit as st
import pandas as pd
import pymongo
import folium


# =========== // CONSTANTS // ===========

LOCAL: bool = False
PALETTE = [
    "#e60000",
    "#ffaa02",
    "#fffe03",
    "#4de600",
    "#0959df"
]

TABLE_COLUMNS = {
    "dam": "Dam Name",
    "this_week": "Percentage Filled",
    "province": "Province",
    "river": "River",
    "full_storage_capacity": "FSC Million m³"
}

# =========== // MAIN PAGE SETUP // ===========

st.set_page_config(
    page_title="Dam Dash",
    page_icon="favicon.svg"
)

if not LOCAL:
    hide_streamlit_style = """
        <style>
            #MainMenu {visibility: hidden;}
            .stAppDeployButton {display:none;}
            footer {visibility: hidden;}
        </style>
    """
    st.markdown(
        hide_streamlit_style,
        unsafe_allow_html=True
    )

# =========== // HELPER FUNCTIONS // ===========


def get_color(value):
    if value < 25:
        return PALETTE[0]
    elif value < 50:
        return PALETTE[1]
    elif value < 75:
        return PALETTE[2]
    elif value < 90:
        return PALETTE[3]
    else:
        return PALETTE[4]


# =========== // MONGO CONNECTION // ===========


@st.cache_resource(ttl='30s')
def init_connection():
    return pymongo.MongoClient(
        f"mongodb+srv://"
        f"{quote(st.secrets['mongo']['username'], safe='')}:"
        f"{quote(st.secrets['mongo']['password'], safe='')}@"
        f"{st.secrets['mongo']['cluster']}"
    )


client: pymongo.MongoClient = init_connection()

# =========== // GET FILTER OPTIONS // ===========


def get_latest_report_date():
    latest_date = client['dam-dash']['reports'].find_one(
        sort=[("report_date", -1)],
        projection={"report_date": 1}
    )
    return latest_date["report_date"] if (
        latest_date
    ) else None


@st.cache_data(ttl=600)
def get_filter_options():
    reports = client['dam-dash']['reports']
    report_dates = sorted(
        reports.distinct("report_date"),
        reverse=True
    )
    provinces = sorted(
        reports.distinct("province")
    )
    return report_dates, provinces

# =========== // DATA FETCH // ===========


@st.cache_data(ttl=10)
def get_data(report_date: list, province: list):
    query = {}
    if report_date != "All":
        query["report_date"] = report_date
    if province != "All":
        query["province"] = province

    items = list(client['dam-dash']['reports'].find(
        filter=query,
        projection={
            k: 1 for k in TABLE_COLUMNS.keys()
        } | {"lat_long": 1}
    ))

    df = pd.DataFrame(items)
    df.rename(
        columns=TABLE_COLUMNS,
        inplace=True
    )
    df[TABLE_COLUMNS['full_storage_capacity']] = df[TABLE_COLUMNS['full_storage_capacity']] / 1e6
    return df

# =========== // FILTERS (in the sidebar) // ===========


report_dates, provinces = get_filter_options()
report_date = st.sidebar.selectbox(
    label="Select Report Date",
    options=["All"] + report_dates,
    index=1 if get_latest_report_date() in report_dates else 0
)

province = st.sidebar.selectbox(
    label="Select Province",
    options=["All"] + provinces
)

display_date = pd.to_datetime(report_date).strftime("%d %B %Y") if report_date != "All" else "All Dates"

# get the data!
data = get_data(report_date, province)

# =========== // BUILD THE MAIN PAGE // ===========


st.title("# SA Dam Dashboard 🌊")
st.write(f"### {display_date} 📆")

left_column, right_column = st.columns([2, 1])

with left_column:
    st.write("#### Dam Levels Table 📊")
    st.dataframe(
        data[list(TABLE_COLUMNS.values())],
        hide_index=True
    )

with right_column:
    st.write("#### Dam Levels Map 🌍")

    min_size, max_size = 6, 15
    min_fsc, max_fsc = data[TABLE_COLUMNS['full_storage_capacity']].min(), data[TABLE_COLUMNS['full_storage_capacity']].max()

    def get_marker_size(fsc):
        return min_size + (max_size - min_size) * ((fsc - min_fsc) / (max_fsc - min_fsc) if max_fsc > min_fsc else 0)

    # Create folium map
    m = folium.Map(
        location=[-28, 24],
        zoom_start=6,
        tiles='OpenStreetMap'
    )
    m.fit_bounds([
        [-35, 16.5],
        [-22, 33]
    ])

    for _, row in data.iterrows():
        folium.CircleMarker(
            location=row["lat_long"],
            radius=get_marker_size(row[TABLE_COLUMNS['full_storage_capacity']]),
            color=get_color(row[TABLE_COLUMNS['this_week']]),
            fill=True,
            fill_color=get_color(row[TABLE_COLUMNS['this_week']]),
            fill_opacity=0.8,
            popup=f"{row[TABLE_COLUMNS['dam']]} ({row[TABLE_COLUMNS['this_week']]}%)"
        ).add_to(m)

    folium_static(m)

# =========== // LEGEND (sidebar) // ===========

st.sidebar.markdown(f"""
### Legend
- <span style='color:{PALETTE[0]};'>● Very Low (0-25)</span>
- <span style='color:{PALETTE[1]};'>● Moderately Low (25-50)</span>
- <span style='color:{PALETTE[2]};'>● Near Normal (50-75)</span>
- <span style='color:{PALETTE[3]};'>● Moderately High (75-90)</span>
- <span style='color:{PALETTE[4]};'>● High (90+)</span>
""", unsafe_allow_html=True)
