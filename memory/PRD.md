# NexaBiz ERP — Product Requirements Document

## Original Problem Statement
The product is a self-hosted ERP template for **NexaBiz** customers, designed for Indonesian and global small businesses — 50-module spec including auth, dashboard, sales, orders, products+variants, inventory, purchasing, production+BOM, HPP calculator, pricing simulator, BEP, finance, P&L, assets, marketplace fees, audit log, notifications, settings. Currency, locale, timezone, and tax settings are configurable per business.

## Architecture
- Backend: FastAPI + MongoDB (motor async), JWT auth, bcrypt password hashing
- Frontend: React 19 + TailwindCSS + Shadcn/UI + Recharts + Sonner toasts
- Design: Minimalist monochrome (Manrope + IBM Plex Sans), Light + Dark mode

## Roles & Permissions (backend-enforced)
- **owner** — configured with `OWNER_EMAIL` / `OWNER_PASSWORD` — full access
- **admin** — sales, orders, products, inventory, customers, suppliers, materials
- **production** — production, inventory, products, materials
- **finance** — finance, reports, purchasing, sales, expenses, assets

## Phase 1 — Delivered (15 Aug 2026)
✅ JWT auth with role-based module access (both frontend routing + backend endpoint validation)
✅ Dashboard KPIs (revenue, orders, COGS, gross+net profit, marketplace fees, cash, inventory value) + health status (Healthy/Warning/Critical)
✅ Charts: Revenue+Profit (30d line), Sales Channel (donut), Top Products (bar), Low Stock alerts
✅ Products CRUD with variants (color × size × stock × cost × price)
✅ Materials CRUD with supplier link
✅ Inventory: variants + materials + full movements log; adjust with recorded movement
✅ Suppliers, Customers, Categories, Expense Categories, Marketplaces, Accounts, Assets — all CRUD
✅ Purchasing: PO → receive increments material stock with weighted-avg cost + auto financial txn
✅ Production: BOM-based orders → complete deducts materials, adds finished goods with weighted-avg cost
✅ Sales: creates order, deducts stock, records COGS, adds financial txn, updates customer stats
✅ Finance: multi-account balances, txn history, expenses per category
✅ HPP Calculator with real-time margin health pill (too_low/safe/healthy/premium)
✅ Pricing Simulator + BEP Calculator with grafik
✅ P&L Report with date range
✅ Settings: theme toggle, categories, marketplaces (editable fees), users (owner), audit log (owner)
✅ Demo data seeded: 4 products, 9 materials, 3 suppliers, 3 customers, 4 marketplaces, Rp 4jt initial capital, 15 sample sales, 3 expenses, heat press asset

## Phase 2 — Delivered (15 Aug 2026)
✅ **Order Cancellation** — `POST /api/sales_orders/{id}/cancel` reverses inventory (restore variant stock via return movement), reverses financial txn (creates negative expense), rolls back customer stats, marks order as `cancelled`/`refunded`
✅ **Onboarding Wizard** — 7-step modal (Business → Currency → Capital → Marketplace → Product → Opening Inventory → Complete). Owner-only. Saves to `settings_kv`, creates Owner Investment txn, optionally seeds first marketplace + product. Accessible via Settings → "Buka Wizard".
✅ **Export & Print** — Backend `/api/reports/export/sales`, `/inventory`, `/profit_loss` streams CSV. Frontend "Sales CSV", "Inventory CSV", "P&L CSV", "Print/PDF" buttons on Reports page + Export CSV button on Sales page.
✅ **Marketplace Import** — Paste CSV export from Shopee/TikTok Shop (columns: `order_number, date, customer_name, sales_channel, variant_sku, quantity, selling_price, discount, shipping, marketplace_fee, advertising_cost`). Preview shows SKU match validation. Bulk `POST /api/marketplace/import` deducts inventory, records COGS, creates financial txn, tags order as `imported=true`. Downloadable template CSV included. Dedicated route `/marketplace-import`.

## Data Integrity Guarantees
- Every stock change writes to `inventory_movements` (before / after / type / user / date)
- Sales creation deducts variant stock, records cost, calculates COGS, appends financial txn if paid, updates customer type/spending
- Sales cancellation restores stock (return movement), reverses financial txn, rolls back customer stats
- Production completion deducts materials via BOM, adds finished goods with weighted-avg cost
- PO receive increments material stock with weighted-avg cost + financial txn if paid
- Marketplace import validates SKU + stock availability before creating any order; skipped rows returned with reason
- Audit log records every create/update/delete/cancel on major entities

## Phase 3 — Backlog
- BOM Templates CRUD UI (currently editable per production order)
- Asset depreciation (straight-line) + monthly journal entries
- Bundle products
- Promotion/voucher engine with negative-margin warning
- Notifications bell (in-app)
- Global search across entities
- 2FA / password reset flow
- Real Shopee/TikTok Shop OAuth partner integration (currently CSV import)

## Test Credentials
See `/app/memory/test_credentials.md`
