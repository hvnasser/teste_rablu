-- Fashion Price Monitor — Supabase schema
-- Run this once in your Supabase SQL editor to create the required tables.

-- -------------------------------------------------------------------------
-- products: one row per (product_url, site) — stable identity
-- -------------------------------------------------------------------------
create table if not exists products (
    id            bigserial primary key,
    site          text        not null,
    brand         text        not null,
    category      text        not null,
    name          text        not null,
    product_url   text        not null,
    image_url     text,
    sku           text,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now(),

    unique (product_url, site)
);

create index if not exists products_brand_idx    on products (brand);
create index if not exists products_site_idx     on products (site);
create index if not exists products_category_idx on products (category);

-- -------------------------------------------------------------------------
-- price_history: one row per scraping run per product
-- -------------------------------------------------------------------------
create table if not exists price_history (
    id               bigserial primary key,
    product_id       bigint      not null references products (id) on delete cascade,
    price            numeric     not null,
    currency         text        not null default 'USD',
    original_price   numeric,
    discount_percent numeric,
    scraped_at       timestamptz not null default now()
);

create index if not exists price_history_product_idx  on price_history (product_id);
create index if not exists price_history_scraped_idx  on price_history (scraped_at desc);

-- -------------------------------------------------------------------------
-- price_alerts: log of every alert sent
-- -------------------------------------------------------------------------
create table if not exists price_alerts (
    id           bigserial primary key,
    alert_type   text        not null,   -- 'price_drop' | 'cross_site_deal'
    product_id   bigint      references products (id) on delete set null,
    message      text        not null,
    triggered_at timestamptz not null default now()
);

-- -------------------------------------------------------------------------
-- Convenience view: latest price per product
-- -------------------------------------------------------------------------
create or replace view latest_prices as
select
    p.id,
    p.site,
    p.brand,
    p.category,
    p.name,
    p.product_url,
    p.image_url,
    ph.price,
    ph.currency,
    ph.original_price,
    ph.discount_percent,
    ph.scraped_at
from products p
join price_history ph on ph.id = (
    select id from price_history
    where product_id = p.id
    order by scraped_at desc
    limit 1
);
