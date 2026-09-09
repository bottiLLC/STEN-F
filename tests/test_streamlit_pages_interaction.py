# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from streamlit.testing.v1 import AppTest


def test_app_main_navigation():
    """Verify that main app.py runs without exceptions and sets up navigation."""
    at = AppTest.from_file("app.py", default_timeout=15)
    at.run()
    assert not at.exception, f"app.py raised exception: {at.exception}"
    assert len(at.sidebar) >= 1


def test_journal_entry_page_render_and_line_controls():
    """Verify that 1_journal_entry.py page renders and line addition/removal works."""
    at = AppTest.from_file("app/ui/app_pages/1_journal_entry.py", default_timeout=15)
    at.run()
    assert not at.exception, f"1_journal_entry.py raised exception: {at.exception}"
    assert len(at.date_input) >= 1
    assert len(at.text_input) >= 2

    # Test adding a line
    add_btn = next((b for b in at.button if "明細行を追加" in b.label), None)
    if add_btn:
        add_btn.click()
        at.run()
        assert not at.exception
        # Test removing the line
        remove_btn = next((b for b in at.button if "行を削除" in b.label), None)
        if remove_btn:
            remove_btn.click()
            at.run()
            assert not at.exception


def test_journal_entry_form_unbalanced_error():
    """Verify that submitting an unbalanced journal entry shows error in UI."""
    at = AppTest.from_file("app/ui/app_pages/1_journal_entry.py", default_timeout=15)
    at.run()

    if len(at.text_input) >= 2 and len(at.selectbox) >= 3 and len(at.number_input) >= 2:
        # Fill description
        at.text_input[0].input("アンバランス仕訳テスト")

        # Select debit account and amount
        at.selectbox[1].select_index(1)
        at.number_input[0].set_value(10000)

        # Select credit account and different amount
        at.selectbox[2].select_index(2)
        at.number_input[1].set_value(5000)  # Unbalanced

        # Click submit button
        submit_btn = next(
            (
                b
                for b in at.button
                if "仕訳帳に登録" in b.label or "登録する" in b.label
            ),
            at.button[-1],
        )
        submit_btn.click()
        at.run()

        assert not at.exception
        # Verify error element is rendered
        assert len(at.error) >= 1
        assert "貸借不一致" in at.error[0].value


def test_journal_entry_form_successful_submission():
    """Verify that submitting a balanced journal entry creates a record and clears state."""
    at = AppTest.from_file("app/ui/app_pages/1_journal_entry.py", default_timeout=15)
    at.run()

    if len(at.text_input) >= 2 and len(at.selectbox) >= 3 and len(at.number_input) >= 2:
        # Set description and counterparty
        at.text_input[0].input("消耗品購入（UIテスト）")
        at.text_input[1].input("テスト文具店")

        # Select balanced debit & credit
        at.selectbox[1].select_index(1)
        at.number_input[0].set_value(3000)

        at.selectbox[2].select_index(2)
        at.number_input[1].set_value(3000)

        # Submit
        submit_btn = next(
            (
                b
                for b in at.button
                if "仕訳帳に登録" in b.label or "登録する" in b.label
            ),
            at.button[-1],
        )
        submit_btn.click()
        at.run()

        assert not at.exception
        assert len(at.error) == 0
        assert "form_entry_key" in at.session_state
        assert at.session_state["form_entry_key"] >= 1
        assert "last_registered_summary" in at.session_state
        assert at.session_state["last_registered_summary"] is not None


def test_journal_entry_ocr_auto_fill_to_voucher():
    """Verify that OCR result automatically populates Step 2 Voucher without showing redundant summary."""
    from app.domain.models.receipt import ReceiptData

    at = AppTest.from_file("app/ui/app_pages/1_journal_entry.py", default_timeout=15)

    dummy_receipt = ReceiptData(
        merchant_name="テストサプライ株式会社",
        transaction_date="2026-08-15",
        total_amount_incl_tax=12800,
        invoice_registration_number="T9876543210987",
        description="オフィス消耗品一式",
        inferred_debit_account_id="1",
        inferred_credit_account_id="2",
    )
    at.session_state["ocr_result"] = dummy_receipt
    at.session_state["form_entry_key"] = 1
    at.run()

    assert not at.exception
    # Step 2 header should be "Step 2: 振替伝票"
    subheaders = [s.value for s in at.subheader]
    assert any("Step 2: 振替伝票" in s for s in subheaders)
    # Redundant AI summary card should not exist
    markdowns = [m.value for m in at.markdown]
    assert not any("AI解析サマリー" in m for m in markdowns)


def test_journal_history_page_interactions():
    """Verify that 2_journal_history.py page renders, filters work, and dataframe displays."""
    at = AppTest.from_file("app/ui/app_pages/2_journal_history.py", default_timeout=15)
    at.run()
    assert not at.exception, f"2_journal_history.py raised exception: {at.exception}"
    assert len(at.date_input) >= 2
    assert len(at.metric) >= 3

    # Filter with keyword
    if len(at.text_input) >= 1:
        at.text_input[0].input("消耗品")
        at.run()
        assert not at.exception

    # Toggle show deleted
    if len(at.checkbox) >= 1:
        at.checkbox[0].check()
        at.run()
        assert not at.exception


def test_general_ledger_page_interactions():
    """Verify that 3_general_ledger.py page renders account summary and ledger table."""
    at = AppTest.from_file("app/ui/app_pages/3_general_ledger.py", default_timeout=15)
    at.run()
    assert not at.exception, f"3_general_ledger.py raised exception: {at.exception}"
    assert len(at.selectbox) >= 2
    assert len(at.metric) >= 4

    # Change selected account
    if len(at.selectbox) >= 2 and len(at.selectbox[1].options) > 1:
        at.selectbox[1].select_index(1)
        at.run()
        assert not at.exception


def test_trial_balance_page_interactions():
    """Verify that 4_trial_balance.py page renders and computes balance checks."""
    at = AppTest.from_file("app/ui/app_pages/4_trial_balance.py", default_timeout=15)
    at.run()
    assert not at.exception, f"4_trial_balance.py raised exception: {at.exception}"
    assert len(at.selectbox) >= 1
    assert len(at.metric) >= 4


def test_financial_statements_page_interactions():
    """Verify that 5_financial_statements.py page renders B/S and P/L and PDF generation."""
    at = AppTest.from_file(
        "app/ui/app_pages/5_financial_statements.py", default_timeout=15
    )
    at.run()
    assert not at.exception, (
        f"5_financial_statements.py raised exception: {at.exception}"
    )
    assert len(at.tabs) >= 1
    assert len(at.checkbox) >= 1  # hide_zero checkbox

    # Toggle hide_zero checkbox
    at.checkbox[0].uncheck()
    at.run()
    assert not at.exception

    # Click PDF generation button
    pdf_btn = next((b for b in at.button if "PDF" in b.label), None)
    if pdf_btn:
        pdf_btn.click()
        at.run()
        assert not at.exception


def test_opening_balance_page_form():
    """Verify that 6_opening_balance.py page renders and validates balanced input."""
    at = AppTest.from_file("app/ui/app_pages/6_opening_balance.py", default_timeout=15)
    at.run()
    assert not at.exception, f"6_opening_balance.py raised exception: {at.exception}"
    assert len(at.number_input) >= 1
    assert len(at.metric) >= 3

    # Set balanced opening numbers if fields exist
    if len(at.number_input) >= 2:
        at.number_input[0].set_value(500000)
        # Find equity / capital input if possible
        at.number_input[-1].set_value(500000)

        submit_btn = next(
            (b for b in at.button if "期首残高を登録" in b.label), at.button[-1]
        )
        submit_btn.click()
        at.run()
        assert not at.exception


def test_master_management_page_tabs_and_forms():
    """Verify that 7_master_management.py page renders all tabs and supports CRUD inputs."""
    at = AppTest.from_file(
        "app/ui/app_pages/7_master_management.py", default_timeout=15
    )
    at.run()
    assert not at.exception, f"7_master_management.py raised exception: {at.exception}"
    assert len(at.tabs) >= 1

    # Corporation info form save
    if len(at.text_input) >= 1:
        at.text_input[0].input("テスト株式会社")
        corp_submit = next((b for b in at.button if "保存" in b.label), at.button[0])
        corp_submit.click()
        at.run()
        assert not at.exception

    # Backup button click
    backup_btn = next((b for b in at.button if "バックアップ" in b.label), None)
    if backup_btn:
        backup_btn.click()
        at.run()
        assert not at.exception
