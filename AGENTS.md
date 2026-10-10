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

### Buttons & Controls
- **Max 1 Primary Button per view:** Styled with Deep Navy background (`#1E3A8A`) and white text. Represents state-changing actions (e.g., Save, Execute).
- **Secondary Buttons:** Ghost style (White background, `#E5E7EB` border, `#1F2937` text).
- **Destructive Buttons:** Only use muted red outline/text, never bright filled red unless confirmation is requested.

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

