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
