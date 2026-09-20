# 📝 Changelog — NexaBiz ERP

All notable changes to this project will be documented in this file.

---

## [2.0.0] - Commercial Template Release

### 🚀 Added
- **Standard Chart of Accounts (COA) & Opening Balance Engine**:
  - Hierarchical account structure: `1-xxxx` Assets, `2-xxxx` Liabilities, `3-xxxx` Equity, `4-xxxx` Revenue, `5-xxxx` COGS, `6-xxxx` Expenses.
  - Automatic balance leveling with `3-10001 Ekuitas Saldo Awal`.
  - Financial statements generator: Balance Sheet (Neraca), Trial Balance (Neraca Saldo), General Ledger (Buku Besar), and Journal Audit Trail.
- **Production-Grade Auth & Security Hardening**:
  - Password complexity validation (minimum 8 characters, required alphanumeric mix).
  - Brute-force protection: Automatic 15-minute IP/account lockout after 5 consecutive failed attempts.
  - User lifecycle management in Settings UI (Create user, deactivate, reset password, change password modal, role assignment).
  - Inactive user blocking at authentication checkpoint.
- **Universal Data & Order Import Wizard**:
  - Unified multi-module importer for Sales Orders, Products & Variants, Materials, Customers, Suppliers, and COA Opening Balances.
  - CSV/TSV parser supporting comma, semicolon, tab, and escaped quotes.
  - Real-time row-by-row dry-run validation endpoint (`POST /api/imports/preview`) highlighting valid and invalid entries with specific error causes.
  - Transactional atomic rollback guarantee (`POST /api/imports/execute` with `@transactional`).
  - Official template generator endpoints (`GET /api/imports/templates/{kind}`).
- **Comprehensive Accountant Export Suite**:
  - Direct CSV export for Profit & Loss, Balance Sheet, Trial Balance, General Ledger, General Journals, Sales Orders, Purchases, and Inventory Valuation.
  - Built-in formal PDF generator via ReportLab formatting formal company headers, date scopes, accounting underlines, and IDR currency alignment.
  - Quick export buttons in FinanceSuite and Calculators pages.
- **Buyer Documentation Package**:
  - `docs/BUYER_GUIDE.md`: Comprehensive onboarding, workflow walkthrough, and setup guide.
  - `docs/FAQ.md`: Frequently asked questions on self-hosting, custom branding, domain & SSL, and database safety.
  - `docs/KNOWN_LIMITATIONS.md`: System boundary clarity, concurrency benchmarks, and architectural design scope.

### 🛡️ Verified & Tested
- 30 automated integration test cases across accounting COA, auth hardening, import wizard, business invariants, and export endpoints (100% passing).
- Zero-warning frontend production compilation with Craco & React.
- Verified Docker compose stack configuration and healthcheck endpoints.
