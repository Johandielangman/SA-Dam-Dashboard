# ~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~
#      /\_/\
#     ( o.o )
#      > ^ <
#
# Author: Johan Hanekom
# Date: January 2025

# ~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~

# =========== // STANDARD IMPORTS // ===========

import time
from urllib.parse import quote

# =========== // CUSTOM IMPORTS // ===========

from streamlit_folium import st_folium
import streamlit as st
import pandas as pd
import pymongo
import folium


# =========== // CONSTANTS // ===========

start_time = time.time()
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
    "province": "Province",
    "river": "River",
    "full_storage_capacity": "FSC Million m³",
    "this_week": "Pct Filled",
}

# =========== // MAIN PAGE SETUP // ===========

st.set_page_config(
    page_title="Dam Dash",
    page_icon="favicon.svg",
    layout="wide",
    initial_sidebar_state="collapsed"
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


@st.cache_data(ttl="30s")
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
        } | {"lat_long": 1, "last_week": 1}
    ))

    df = pd.DataFrame(items)
    df.rename(
        columns=TABLE_COLUMNS,
        inplace=True
    )
    df[TABLE_COLUMNS['full_storage_capacity']] = df[TABLE_COLUMNS['full_storage_capacity']] / 1e6

    # Compute percentage change
    df["Change"] = df.apply(
        lambda row: (
            f'🔼 {row["Pct Filled"] - row["last_week"]:.1f}%' if (
                row["Pct Filled"] > row["last_week"]
            ) else (
                f'🔻 {row["Pct Filled"] - row["last_week"]:.1f}%'
            ) if (
                row["Pct Filled"] < row["last_week"]
            )else '◼ 0%'
        ), axis=1)
    df.drop(columns=["last_week"], inplace=True)

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
st.title("South Africa Dam Dashboard 💧")
st.write(f"### Report Date: **{display_date}** 📆")
st.write("**Welcome to the South African Dam Dashboard!** This dashboard provides weekly updates on dam levels across South Africa, with data sourced from the [Department of Water and Sanitation](https://www.dws.gov.za/hydrology/Weekly/Province.aspx). The information is presented in both a table and an interactive map. By default, the table is sorted by province and percentage filled. Filters are available in the sidebar, allowing you to refine the data by report date and province. By default, the latest available data is shown for all provinces. On the map, each dot represents a dam location. The color of the dot indicates the dam's water level (see the legend in the sidebar), while the dot's size reflects the dam's storage capacity—larger dots represent larger dams. The table also includes a **difference column**, comparing each dam's current percentage filled to the previous week's value, indicating whether the level has increased 🔼 or decreased 🔻. Feel free to download the data as a CSV.")

with st.spinner('Fetching data...'):
    data = get_data(report_date, province)

# =========== // BUILD THE MAIN PAGE // ===========

left_column, right_column = st.columns(
    [1, 2],
    gap="medium"
)

with left_column:
    st.write("#### Dam Levels Table 📊")
    data.sort_values(by=[TABLE_COLUMNS['province'], TABLE_COLUMNS['this_week']], ascending=[True, False], inplace=True)
    st.dataframe(
        data[list(TABLE_COLUMNS.values()) + ["Change"]],
        hide_index=True
    )
    st.write("[![BuyMeACoffee](https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/johanlangman)")


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

    st_folium(m, height=500, use_container_width=True, returned_objects=[])

# =========== // LEGEND (sidebar) // ===========

st.sidebar.markdown(f"""
### Legend
- <span style='color:{PALETTE[0]};'>● Very Low (0-25)</span>
- <span style='color:{PALETTE[1]};'>● Moderately Low (25-50)</span>
- <span style='color:{PALETTE[2]};'>● Near Normal (50-75)</span>
- <span style='color:{PALETTE[3]};'>● Moderately High (75-90)</span>
- <span style='color:{PALETTE[4]};'>● High (90+)</span>
""", unsafe_allow_html=True)


# =========== // SORRY IT TOOK SO LONG // ===========
if time.time() - start_time > 10:
    msg = st.toast('Hi!', icon="🛑")
    time.sleep(3)
    msg.toast('If things feel slow...', icon="🛑")
    time.sleep(3)
    msg.toast('Remember that this is hosted on an old laptop!', icon="🛑")
    time.sleep(3)
    msg.toast('Thanks! And enjoy!', icon="🎉")
