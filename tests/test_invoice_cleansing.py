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

import pytest
from datetime import date
from pydantic import ValidationError
from app.domain.models.counterparty import Counterparty
from app.domain.models.transaction import Transaction, TransactionLine


def test_counterparty_invoice_number_cleansing():
    """Ensure that empty string or whitespace-only invoice_number on Counterparty is cleansed to None."""
    # 1. Valid T-number should pass
    cp_valid = Counterparty(name="Test Corp", invoice_number="T1234567890123")
    assert cp_valid.invoice_number == "T1234567890123"

    # 2. None should pass
    cp_none = Counterparty(name="Test Corp", invoice_number=None)
    assert cp_none.invoice_number is None

    # 3. Empty string should be cleansed to None and pass
    cp_empty = Counterparty(name="Test Corp", invoice_number="")
    assert cp_empty.invoice_number is None

    # 4. Whitespace string should be cleansed to None and pass
    cp_spaces = Counterparty(name="Test Corp", invoice_number="   ")
    assert cp_spaces.invoice_number is None

    # 5. Invalid format should still fail validation
    with pytest.raises(ValidationError):
        Counterparty(name="Test Corp", invoice_number="invalid-format")


def test_transaction_invoice_number_cleansing():
    """Ensure that empty string or whitespace-only invoice_number on Transaction is cleansed to None."""
    lines = [
        TransactionLine(account_id=1, debit=1000, credit=0),
        TransactionLine(account_id=2, debit=0, credit=1000),
    ]

    # 1. Valid T-number should pass
    tx_valid = Transaction(
        date=date.today(),
        description="Valid Tx",
        lines=lines,
        invoice_number="T1234567890123",
    )
    assert tx_valid.invoice_number == "T1234567890123"

    # 2. None should pass
    tx_none = Transaction(
        date=date.today(),
        description="None Tx",
        lines=lines,
        invoice_number=None,
    )
    assert tx_none.invoice_number is None

    # 3. Empty string should be cleansed to None and pass
    tx_empty = Transaction(
        date=date.today(),
        description="Empty Tx",
        lines=lines,
        invoice_number="",
    )
    assert tx_empty.invoice_number is None

    # 4. Whitespace string should be cleansed to None and pass
    tx_spaces = Transaction(
        date=date.today(),
        description="Spaces Tx",
        lines=lines,
        invoice_number="   ",
    )
    assert tx_spaces.invoice_number is None

    # 5. Invalid format should still fail validation
    with pytest.raises(ValidationError):
        Transaction(
            date=date.today(),
            description="Invalid Tx",
            lines=lines,
            invoice_number="invalid-format",
        )
