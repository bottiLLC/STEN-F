# Local Rules: Financial & Accounting Invariants

## 1. Absolute Immutability (Append-Only & No Update/Delete)
- **Rule**: The generation of code to execute UPDATE or DELETE operations on the Journal Entries table is strictly prohibited.
- **Correction Method Constraint**: Errors must be rectified solely by inserting a new "reversing entry" (or "red slip")—with debits and credits inverted—rather than by overwriting historical records.

## 2. Zero-Tolerance Balance (Debit-Credit Equality)
- **Rule**: A transaction cannot be committed unless the sum of its line items satisfies the condition `SUM(debit_amount) - SUM(credit_amount) == 0` without exception.
- **Data Type and Calculation Constraint**: The use of floating-point numbers (Float/Double) for monetary calculations is prohibited; fixed-point types (e.g., Decimal, BigInt) appropriate to the language specification must be used.

## 3. Dual-Timestamp Separation
- **Rule**: Transaction timestamps must be maintained across two axes: the "transaction occurrence date" (`occurred_at` / business date) and the "system recording timestamp" (`recorded_at` / immutable UTC timestamp).

## 4. Projection Separation for Ledgers and Balances (Projection Pattern)
- **Rule**: General ledgers and account balance tables must be treated as "caches (projections) derived from the journal log"; direct manual input of numerical values into these tables is strictly prohibited.

---

# STEN-F UI/UX Design System Rules

## Core Philosophy
- Aesthetic: Industrial minimalism, solid financial terminal, high-precision instrument tool.
- Visual hierarchy: Dictated by typography, alignment, and subtle borders—never by arbitrary colors.
- Principle: Monochromatic foundation (90%) with a single semantic/functional accent color.

## 1. Color Palette (Strict Enforcement)
Never invent arbitrary hex colors. Stick strictly to these tokens:
- **Base Background:** `#FFFFFF` (Main canvas)
- **Surface / Card Background:** `#F8F9FA` to `#F1F3F5` (Subtle grey for containers/stripes)
- **Border / Divider:** `#E5E7EB` (Subtle 1px boundaries)
- **Text Primary:** `#1F2937` (Dark slate, do NOT use pure black `#000000`)
- **Text Muted:** `#6B7280` (Secondary metadata, timestamps, captions)
- **Primary Action (Brand Cold Accent):** `#1E3A8A` (Deep Industrial Navy) or `#2563EB` (for active hover states only)
- **Semantic / Status (Use Sparingly):**
  - Danger / Imbalance: `#DC2626`
  - Success / Balanced: `#059669`

## 2. Component Guidelines

### Buttons & Action Controls (Standardized Ergonomics)
- **Sizing Constraints:**
  - NEVER use full-width buttons (`width: 100%`) across desktop screens. Buttons must maintain compact industrial dimensions.
  - Standard sizing: `width: auto; min-width: 140px; max-width: 220px; height: 38px;` with compact internal padding (`padding: 0.5rem 1.25rem;`).
  - Table-row action buttons (e.g., Edit, Delete, View) must be ultra-compact (`height: 28px; padding: 0.25rem 0.75rem; font-size: 0.85rem;`).

- **Placement & Alignment:**
  - **Form Submissions:** Always align the primary submission action to the **BOTTOM-RIGHT** of the form card or input block, following standard Z-pattern gaze exit points.
  - **Secondary Actions (Cancel, Reset):** Place to the LEFT of the primary button with a consistent `8px` or `12px` gap. Never stack them vertically unless screen width is strictly constrained.
  - **Toolbars & Header Actions:** Align to the top-right or right edge of the card/section header.

- **Button Hierarchy (Per View):**
  - **Primary (Max 1 per section):** Solid Deep Navy (`#1E3A8A`), white text, bold font-weight (500). Reserved for final commits (Save, Apply, Register).
  - **Secondary / Ghost:** White background, subtle border (`#E5E7EB`), text (`#1F2937`). For auxiliary operations.
  - **Destructive:** White background, muted red border/text (`#DC2626`). Turn solid red ONLY upon critical confirmation modals.

- **Labeling & Microcopy (Strictly Concise):**
  - Buttons must be treated like industrial hardware switches, NOT conversational prompts.
  - **Single verb or concise noun phrase only:** Maximum 2 to 6 Japanese characters (or 1 to 2 English words).
  - **STRICT PROHIBITION of conversational fluff:** Never use prefixes like "今すぐ..." (Now/Immediately) or redundant suffixes like "...を実行" (...Execute) / "...を行う" (...Perform).
    - ❌ BAD: `今すぐバックアップを実行` (Run backup right now)
    - ⭕️ GOOD: `バックアップ` (Backup) or `バックアップ作成` (Create Backup)
    - ❌ BAD: `自社情報を保存する` (Save company info)
    - ⭕️ GOOD: `保存` (Save)
    - ❌ BAD: `CSVデータを出力する`
    - ⭕️ GOOD: `CSV出力` (Export CSV)

- **Layout & Wrapping Constraints:**
  - **No Text Wrapping:** Enforce `white-space: nowrap;` across all buttons. Button labels must NEVER wrap into multiple lines under any viewport size.
  - **Icon & Text Alignment:** If an icon is included, keep a fixed `gap: 6px;` and ensure strict vertical centering (`display: inline-flex; align-items: center; justify-content: center;`). Icons must never float or wrap separately from the text.

### Tables & Accounting Grids (B/S & P/L)
- **Typography:** Always apply `font-variant-numeric: tabular-nums;` to financial amounts. Right-align all numeric values.
- **Alignment:** Balance Sheet (B/S) must maintain bottom alignment (equal visual height) between Assets and Liabilities/Equity.
- **P/L Structure:** Always single-column waterfall (vertical cascading), never split into side-by-side columns.
- **Subtotals:** 1px solid top border (`#E5E7EB`).
- **Grand Totals:** Light grey background fill (`#F8F9FA`), double bottom border (`border-bottom: 3px double #1F2937`), font-weight bold. Do NOT change text font color.

### Iconography & Content Hygiene
- **STRICT PROHIBITION:** Do NOT use emojis (e.g., 💾, 📰, 🗓️, 🏢) in headings, labels, or buttons.
- Use only clean, single-color line icons (Feather/Streamlit native icons) or purely textual labels.
- Set uniform `border-radius: 4px;` across all cards, inputs, and buttons (sharp engineering radius, avoid round pill shapes).

## 3. Implementation Guardrails (Streamlit Specific)
- Custom CSS must be scoped and injected cleanly.
- Prefer CSS Grid/Flexbox in raw HTML containers (`st.markdown(..., unsafe_allow_html=True)`) over nested native `st.columns` when strict dimensional alignment (like B/S sheets) is required.
- When rendering native `st.button` inside forms, do NOT set `use_container_width=True` on full-width columns. Instead, wrap in narrow columns (e.g., `st.columns([4, 1])`) to naturally constrain horizontal span.