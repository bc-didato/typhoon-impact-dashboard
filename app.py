"""Philippine Typhoon Impact Dashboard, 2014-2020 (ITD112 final project).

Run:  streamlit run app.py
Needs typhoon_impact_clean.xlsx in the same folder as this file.
Optional: data/provinces.geojson enables the choropleth map (chart 2).
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

HERE = Path(__file__).parent
XLSX = HERE / "typhoon_impact_clean.xlsx"
GEOJSON = HERE / "data" / "provinces.geojson"
GEO_KEY = "properties.adm2_en"  # property in data/provinces.geojson that holds province names
# data uses older province names than the 2023 boundary file
PROVINCE_ALIAS = {"Western Samar": "Samar"}

st.set_page_config(page_title="Philippine Typhoon Impact, 2014–2020", layout="wide")

# Okabe-Ito (color-blind safe) for categories, Blues for counts
ISLAND_COLORS = {"Luzon": "#0072B2", "Visayas": "#E69F00", "Mindanao": "#009E73"}
SEQ = px.colors.sequential.Blues[2:]
ISLAND_GROUP = {
    **dict.fromkeys(["NCR", "CAR", "I", "II", "III", "IV-A", "IV-B", "V"], "Luzon"),
    **dict.fromkeys(["VI", "VII", "VIII", "NIR"], "Visayas"),
    **dict.fromkeys(["IX", "X", "XI", "XII", "XIII", "ARMM"], "Mindanao"),
}
MEASURES = {
    "Persons affected": "persons_affected",
    "Families affected": "families_affected",
    "Houses damaged": "houses_damaged_total",
}


@st.cache_data
def load():
    reg = pd.read_excel(XLSX, sheet_name="region_level")
    prov = pd.read_excel(XLSX, sheet_name="province_level")
    mun = pd.read_excel(XLSX, sheet_name="clean_municipality")
    for d in (reg, prov, mun):
        d["island_group"] = d["region"].map(ISLAND_GROUP)
    return reg, prov, mun


if not XLSX.exists():
    st.error(f"Put typhoon_impact_clean.xlsx in this folder: {HERE}")
    st.stop()

reg, prov, mun = load()

# ---------------- Sidebar filters ----------------
st.sidebar.header("Filters")
years = sorted(reg["year"].unique())
sel_years = st.sidebar.multiselect("Year", years, default=years)
typh_opts = sorted(reg.loc[reg["year"].isin(sel_years), "typhoon"].unique())
sel_typh = st.sidebar.multiselect("Typhoon (empty = all)", typh_opts)
regions = sorted(reg["region"].unique())
sel_reg = st.sidebar.multiselect("Region (empty = all)", regions)
measure_label = st.sidebar.selectbox("Measure", list(MEASURES))
measure = MEASURES[measure_label]


def filt(d):
    d = d[d["year"].isin(sel_years)]
    if sel_typh:
        d = d[d["typhoon"].isin(sel_typh)]
    if sel_reg:
        d = d[d["region"].isin(sel_reg)]
    return d


r, p, m = filt(reg), filt(prov), filt(mun)

st.title("Philippine Typhoon Impact Dashboard, 2014–2020")
st.caption("Source: Netherlands Red Cross (510) from NDRRMC DROMIC reports, via HDX. "
           "No data for 2017. Blank = not reported (shown gray), not zero.")

if r.empty:
    st.warning("No data for this filter combination.")
    st.stop()

# ---------------- KPI cards ----------------
c = st.columns(4)
c[0].metric("Typhoons", r["typhoon"].nunique())
c[1].metric("Persons affected", f"{r['persons_affected'].sum():,.0f}")
c[2].metric("Families affected", f"{r['families_affected'].sum():,.0f}")
c[3].metric("Houses damaged", f"{r['houses_damaged_total'].sum():,.0f}",
            help="Excludes rows where houses damaged were not reported.")

# ---------------- Row 1: chart 2 (map) + chart 4 (top 10) ----------------
left, right = st.columns([3, 2])

with left:
    st.subheader("2 · Where is impact highest?")
    prov_tot = (p.groupby(["province", "region"], as_index=False)[measure]
                .sum(min_count=1).dropna(subset=[measure]))
    if GEOJSON.exists():
        gj = json.loads(GEOJSON.read_text(encoding="utf-8"))
        prov_tot["province"] = prov_tot["province"].replace(PROVINCE_ALIAS)
        prov_tot = prov_tot.groupby("province", as_index=False)[measure].sum()
        fig = px.choropleth(prov_tot, geojson=gj, locations="province",
                            featureidkey=GEO_KEY, color=measure,
                            color_continuous_scale=SEQ,
                            labels={measure: measure_label})
        # gray base layer: provinces with no report stay visible (not zero)
        names = [f["properties"]["adm2_en"] for f in gj["features"]]
        base = go.Choropleth(geojson=gj, locations=names, z=[0] * len(names),
                             featureidkey=GEO_KEY, showscale=False, hoverinfo="skip",
                             colorscale=[[0, "#d9d9d9"], [1, "#d9d9d9"]],
                             marker_line_color="white", marker_line_width=0.3)
        fig.add_trace(base)
        fig.data = (fig.data[-1],) + fig.data[:-1]  # draw gray base first
        fig.update_geos(bgcolor="rgba(0,0,0,0)")
        fig.update_traces(marker_line_color="white", marker_line_width=0.3)
    else:
        st.info("No data/provinces.geojson found, so a ranked bar of the top 15 "
                "provinces is shown instead. Add the boundary file to get the map.")
        top = prov_tot.nlargest(15, measure).sort_values(measure)
        fig = px.bar(top, x=measure, y="province", orientation="h", color=measure,
                     color_continuous_scale=SEQ, hover_data=["region"],
                     labels={measure: measure_label, "province": ""})
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=420)
    st.plotly_chart(fig, width="stretch")

with right:
    st.subheader("4 · Top 10 municipalities / cities")
    mm = m.dropna(subset=[measure]).copy()
    if mm.empty:
        st.info("No municipality rows for this selection (six typhoons have only "
                "province/region totals).")
    else:
        mm["place"] = (mm["municipality_or_city"] + ", " + mm["province"].fillna("n/a")
                       + " (" + mm["typhoon"].str.title() + ")")
        top = mm.nlargest(10, measure).sort_values(measure)
        fig = px.bar(top, x=measure, y="place", orientation="h",
                     color_discrete_sequence=["#2f6f9f"],
                     labels={measure: measure_label, "place": ""})
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=420)
        st.plotly_chart(fig, width="stretch")

# ---------------- Row 2: chart 1 (typhoons by year) ----------------
st.subheader("1 · Which typhoons were most severe?")
ty = (r.groupby(["typhoon", "year"], as_index=False)[measure].sum(min_count=1)
      .sort_values(["year", "typhoon"]))
ty["typhoon"] = ty["typhoon"].str.title()
fig = px.bar(ty, x="typhoon", y=measure, color="year", color_continuous_scale=SEQ,
             labels={measure: measure_label, "typhoon": ""},
             category_orders={"typhoon": ty["typhoon"].tolist()})
fig.update_coloraxes(colorbar_title="Year")
fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=380)
st.plotly_chart(fig, width="stretch")

# ---------------- Row 3: chart 3 (heatmap) + chart 5 (scatter) ----------------
h, s = st.columns(2)

with h:
    st.subheader("3 · Which regions are hit repeatedly?")
    pv = r.pivot_table(index="region", columns="year", values=measure,
                       aggfunc="sum", dropna=False)
    pv = pv.reindex(columns=years)
    # no report -> NaN (gray); a real 0 stays 0
    mask = r.groupby(["region", "year"])[measure].apply(lambda x: x.notna().any()).unstack()
    mask = mask.reindex(index=pv.index, columns=pv.columns).fillna(False)
    pv = pv.where(mask)
    fig = go.Figure(go.Heatmap(z=pv.values, x=[str(y) for y in pv.columns], y=list(pv.index),
                               colorscale=SEQ, hoverongaps=False,
                               colorbar=dict(title=measure_label)))
    fig.update_xaxes(type="category")
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=420,
                      plot_bgcolor="#d9d9d9")
    st.plotly_chart(fig, width="stretch")
    st.caption("Gray cell = not reported for that region and year.")

with s:
    st.subheader("5 · Families affected vs. damaged houses")
    sc = (p.groupby(["province", "region", "island_group"], as_index=False)
          .agg(families=("families_affected", "sum"),
               houses=("houses_damaged_total", lambda x: x.sum(min_count=1)),
               barangays=("brgys_affected", "sum")))
    sc = sc[(sc["families"] > 0) & (sc["houses"] > 0)]
    if sc.empty:
        st.info("Not enough data for this selection.")
    else:
        fig = px.scatter(sc, x="families", y="houses", size="barangays",
                         color="island_group", color_discrete_map=ISLAND_COLORS,
                         hover_name="province", log_x=True, log_y=True,
                         labels={"families": "Families affected (log scale)",
                                 "houses": "Houses damaged (log scale)",
                                 "island_group": "Island group",
                                 "barangays": "Barangays"})
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=420)
        st.plotly_chart(fig, width="stretch")
        st.caption("Point size = barangays affected. Both axes are logarithmic.")

# ---------------- Export + limitations ----------------
st.download_button("Download filtered municipality table (CSV)",
                   m.drop(columns=["island_group"]).to_csv(index=False).encode("utf-8"),
                   "typhoon_municipality_filtered.csv", "text/csv")
with st.expander("Data limitations"):
    st.markdown(
        "- Only six years are reported (no 2017); year is the only time field.\n"
        "- Casualty columns are mostly empty and are not used.\n"
        "- Province and region totals are as reported and are never added to "
        "municipality rows.\n"
        "- \"Persons affected\" are event counts, not unique people.\n"
        "- Six typhoons have no municipality rows (Amang, Ineng, Karen, Lawin, Nina, Nona)."
    )