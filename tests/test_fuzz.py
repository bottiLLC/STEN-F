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

from __future__ import annotations

from datetime import date
import re
from hypothesis import given, strategies as st
from pydantic import ValidationError
import pytest

from app.domain_contracts import Transaction, TransactionLine


@pytest.mark.fuzz
@given(
    debit_val=st.integers(min_value=0, max_value=100000000),
    credit_val=st.integers(min_value=0, max_value=100000000),
)
def test_fuzz_transaction_balance_validates_debit_credit_equality(
    debit_val: int, credit_val: int
) -> None:
    """Fuzz test for Transaction model balance validation using hypothesis.

    Args:
        debit_val: Fuzzed integer debit value.
        credit_val: Fuzzed integer credit value.
    """
    # Arrange
    lines = [
        TransactionLine(account_id=1, debit=debit_val, credit=0),
        TransactionLine(account_id=2, debit=0, credit=credit_val),
    ]

    # Act & Assert
    if debit_val == credit_val:
        tx = Transaction(
            date=date.today(),
            description="Fuzz test transaction",
            lines=lines,
        )
        assert sum(line.debit for line in tx.lines) == debit_val
        assert tx.lines[0].debit == debit_val
        assert tx.lines[1].credit == credit_val
    else:
        with pytest.raises(ValidationError, match="Unbalanced Transaction"):
            Transaction(
                date=date.today(),
                description="Fuzz test transaction",
                lines=lines,
            )


@pytest.mark.fuzz
@given(inv_num=st.text())
def test_fuzz_invoice_number_cleansing_and_validation(inv_num: str) -> None:
    """Fuzz test for Transaction invoice_number field formatting and pattern verification.

    Args:
        inv_num: Fuzzed string input for invoice number.
    """
    # Arrange
    lines = [
        TransactionLine(account_id=1, debit=1000, credit=0),
        TransactionLine(account_id=2, debit=0, credit=1000),
    ]
    is_valid_format = re.match(r"^T[0-9]{13}$", inv_num.strip()) is not None
    is_empty_or_whitespace = inv_num.strip() == ""

    # Act & Assert
    if is_valid_format:
        tx = Transaction(
            date=date.today(),
            description="Invoice formatting fuzz",
            lines=lines,
            invoice_number=inv_num,
        )
        assert tx.invoice_number == inv_num.strip()
    elif is_empty_or_whitespace:
        tx = Transaction(
            date=date.today(),
            description="Invoice formatting fuzz",
            lines=lines,
            invoice_number=inv_num,
        )
        assert tx.invoice_number is None
    else:
        with pytest.raises(ValidationError, match="String should match pattern"):
            Transaction(
                date=date.today(),
                description="Invoice formatting fuzz",
                lines=lines,
                invoice_number=inv_num,
            )
