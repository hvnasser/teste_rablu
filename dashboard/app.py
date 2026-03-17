"""
Fashion Price Monitor — Streamlit dashboard.

Run with:
    streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
import os

# Ensure project root is on the path when running from dashboard/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import BRANDS, CATEGORIES, SITES
from database.operations import (
    get_cross_site_prices,
    get_latest_prices,
    get_price_history,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Fashion Price Monitor",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("👗 Fashion Price Monitor")
st.caption("Real-time luxury fashion price tracking across major retailers")

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Filters")

    selected_brands = st.multiselect(
        "Brands",
        options=list(BRANDS.keys()),
        default=list(BRANDS.keys()),
        format_func=lambda k: BRANDS[k]["display_name"],
    )

    selected_sites = st.multiselect(
        "Sites",
        options=list(SITES.keys()),
        default=list(SITES.keys()),
        format_func=lambda k: SITES[k]["display_name"],
    )

    selected_categories = st.multiselect(
        "Categories",
        options=CATEGORIES,
        default=CATEGORIES,
    )

    only_on_sale = st.checkbox("Only show discounted products", value=False)

    st.divider()
    st.caption("Data refreshes on each page reload.")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def load_prices(brands, sites, categories):
    rows = []
    for brand in (brands or list(BRANDS.keys())):
        for site in (sites or list(SITES.keys())):
            for category in (categories or CATEGORIES):
                rows.extend(get_latest_prices(brand=brand, site=site, category=category))
    return pd.DataFrame(rows)


df = load_prices(selected_brands, selected_sites, selected_categories)

if df.empty:
    st.warning("No data found. Run `python main.py` first to collect prices.")
    st.stop()

# Normalise
df["brand_label"] = df["brand"].map(
    lambda k: BRANDS.get(k, {}).get("display_name", k)
)
df["site_label"] = df["site"].map(
    lambda k: SITES.get(k, {}).get("display_name", k)
)
df["scraped_at"] = pd.to_datetime(df["scraped_at"])

if only_on_sale:
    df = df[df["discount_percent"].notna() & (df["discount_percent"] > 0)]

# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total products tracked", len(df))
col2.metric("Sites active", df["site"].nunique())
col3.metric(
    "Avg discount",
    f"{df['discount_percent'].mean():.1f}%" if not df["discount_percent"].isna().all() else "N/A",
)
best_row = df.loc[df["discount_percent"].idxmax()] if not df["discount_percent"].isna().all() else None
if best_row is not None:
    col4.metric(
        "Best deal today",
        f"{best_row['discount_percent']:.0f}% off",
        delta=best_row["site_label"],
    )

st.divider()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_overview, tab_compare, tab_history, tab_table = st.tabs(
    ["📊 Overview", "🔍 Compare Sites", "📈 Price History", "📋 Full Table"]
)

# ----- Overview tab -----
with tab_overview:
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Products per site")
        count_site = df.groupby("site_label").size().reset_index(name="count")
        fig = px.bar(
            count_site,
            x="site_label",
            y="count",
            color="site_label",
            labels={"site_label": "Site", "count": "Products"},
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Average discount by brand")
        disc = (
            df.groupby("brand_label")["discount_percent"]
            .mean()
            .dropna()
            .reset_index()
        )
        fig2 = px.bar(
            disc,
            x="brand_label",
            y="discount_percent",
            color="brand_label",
            labels={"brand_label": "Brand", "discount_percent": "Avg discount (%)"},
            color_discrete_sequence=px.colors.qualitative.Pastel2,
        )
        fig2.update_layout(showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Price distribution by category")
    fig3 = px.box(
        df,
        x="category",
        y="price",
        color="brand_label",
        points="outliers",
        labels={"category": "Category", "price": f"Price ({df['currency'].iloc[0]})"},
    )
    st.plotly_chart(fig3, use_container_width=True)

# ----- Compare Sites tab -----
with tab_compare:
    st.subheader("Cross-site price comparison")

    brand_choice = st.selectbox(
        "Select brand",
        options=selected_brands,
        format_func=lambda k: BRANDS[k]["display_name"],
    )
    category_choice = st.selectbox("Select category", options=selected_categories)

    subset = df[(df["brand"] == brand_choice) & (df["category"] == category_choice)]

    if subset.empty:
        st.info("No data for this combination.")
    else:
        pivot = (
            subset.groupby(["name", "site_label"])["price"]
            .min()
            .unstack("site_label")
            .reset_index()
        )
        pivot["cheapest_site"] = pivot.iloc[:, 1:].idxmin(axis=1)
        pivot["min_price"] = pivot.iloc[:, 1:-1].min(axis=1)
        pivot["max_price"] = pivot.iloc[:, 1:-1].max(axis=1)
        pivot["price_spread_%"] = (
            (pivot["max_price"] - pivot["min_price"]) / pivot["max_price"] * 100
        ).round(1)

        fig4 = px.bar(
            subset,
            x="name",
            y="price",
            color="site_label",
            barmode="group",
            labels={"name": "Product", "price": "Price (USD)", "site_label": "Site"},
            title=f"{BRANDS[brand_choice]['display_name']} — {category_choice.title()} prices",
        )
        fig4.update_xaxes(tickangle=30)
        st.plotly_chart(fig4, use_container_width=True)

        st.caption("Products with biggest price spread across sites:")
        st.dataframe(
            pivot[["name", "min_price", "max_price", "price_spread_%", "cheapest_site"]]
            .sort_values("price_spread_%", ascending=False)
            .head(10),
            use_container_width=True,
        )

# ----- Price History tab -----
with tab_history:
    st.subheader("Price history for a product")

    product_names = sorted(df["name"].unique())
    selected_product = st.selectbox("Select product", options=product_names)

    product_row = df[df["name"] == selected_product].iloc[0]
    product_id = int(product_row["id"])

    @st.cache_data(ttl=300)
    def load_history(pid):
        return pd.DataFrame(get_price_history(pid))

    hist_df = load_history(product_id)

    if hist_df.empty:
        st.info("No price history available yet.")
    else:
        hist_df["scraped_at"] = pd.to_datetime(hist_df["scraped_at"])
        fig5 = go.Figure()
        fig5.add_trace(
            go.Scatter(
                x=hist_df["scraped_at"],
                y=hist_df["price"],
                mode="lines+markers",
                name="Price",
                line={"color": "#e91e8c", "width": 2},
            )
        )
        if hist_df["original_price"].notna().any():
            fig5.add_trace(
                go.Scatter(
                    x=hist_df["scraped_at"],
                    y=hist_df["original_price"],
                    mode="lines",
                    name="Original price",
                    line={"dash": "dash", "color": "gray"},
                )
            )
        fig5.update_layout(
            title=f"Price history — {selected_product}",
            xaxis_title="Date",
            yaxis_title=f"Price ({product_row.get('currency', 'USD')})",
            hovermode="x unified",
        )
        st.plotly_chart(fig5, use_container_width=True)

# ----- Full Table tab -----
with tab_table:
    st.subheader("All tracked products")

    display_cols = [
        "brand_label", "category", "site_label", "name",
        "price", "currency", "original_price", "discount_percent",
        "scraped_at",
    ]
    available = [c for c in display_cols if c in df.columns]

    sort_col = st.selectbox("Sort by", ["discount_percent", "price", "scraped_at"], index=0)
    st.dataframe(
        df[available]
        .rename(columns={"brand_label": "brand", "site_label": "site"})
        .sort_values(sort_col, ascending=False)
        .reset_index(drop=True),
        use_container_width=True,
        column_config={
            "price": st.column_config.NumberColumn(format="$%.2f"),
            "original_price": st.column_config.NumberColumn(format="$%.2f"),
            "discount_percent": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

    csv = df[available].to_csv(index=False).encode()
    st.download_button("Download CSV", csv, "fashion_prices.csv", "text/csv")
