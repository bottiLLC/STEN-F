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
import re
from datetime import date
from pydantic import ValidationError
from hypothesis import given, strategies as st

from app.domain.models.transaction import Transaction, TransactionLine


@pytest.mark.fuzz
@given(
    debit_val=st.integers(min_value=0, max_value=100000000),
    credit_val=st.integers(min_value=0, max_value=100000000),
)
def test_fuzz_transaction_balance(debit_val: int, credit_val: int):
    """
    Fuzz test for Transaction model balance validation using hypothesis.
    Ensures that ValidationError is raised if and only if debit != credit.
    """
    lines = [
        TransactionLine(account_id=1, debit=debit_val, credit=0),
        TransactionLine(account_id=2, debit=0, credit=credit_val),
    ]

    if debit_val == credit_val:
        # Balanced, should successfully instantiate
        tx = Transaction(
            date=date.today(),
            description="Fuzz test transaction",
            lines=lines,
        )
        assert tx is not None
    else:
        # Unbalanced, must raise ValidationError
        with pytest.raises(ValidationError):
            Transaction(
                date=date.today(),
                description="Fuzz test transaction",
                lines=lines,
            )


@pytest.mark.fuzz
@given(inv_num=st.text())
def test_fuzz_invoice_format(inv_num: str):
    """
    Fuzz test for Transaction invoice_number field formatting.
    Ensures that validation enforces the correct format (^T[0-9]{13}$).
    """
    lines = [
        TransactionLine(account_id=1, debit=1000, credit=0),
        TransactionLine(account_id=2, debit=0, credit=1000),
    ]

    is_valid_format = re.match(r"^T[0-9]{13}$", inv_num) is not None

    if is_valid_format:
        # Valid format, should succeed
        tx = Transaction(
            date=date.today(),
            description="Invoice formatting fuzz",
            lines=lines,
            invoice_number=inv_num,
        )
        assert tx.invoice_number == inv_num
    else:
        # Invalid format, must raise ValidationError
        with pytest.raises(ValidationError):
            Transaction(
                date=date.today(),
                description="Invoice formatting fuzz",
                lines=lines,
                invoice_number=inv_num,
            )
