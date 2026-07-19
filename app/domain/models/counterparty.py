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

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Counterparty(BaseModel):
    id: Optional[int] = None
    name: str
    name_kana: Optional[str] = None
    invoice_number: Optional[str] = Field(
        None, pattern=r"^T[0-9]{13}$", description="T番号 (T + 13 digits)"
    )
    debit_account_id: Optional[int] = None
    credit_account_id: Optional[int] = None
    description_template: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @field_validator("invoice_number", mode="before")
    @classmethod
    def clean_invoice_number(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            v_stripped = v.strip()
            return v_stripped if v_stripped else None
        return v
