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

from typing import Any
from decimal import Decimal, ROUND_HALF_UP


_TRANS_MAP = str.maketrans({"０": "0", "１": "1", "２": "2", "３": "3", "４": "4", "５": "5", "６": "6", "７": "7", "８": "8", "９": "9", "，": "", ",": "", "　": "", " ": ""})


def normalize_amount(value: Any) -> int:
    """
    金額値をクレンジングして安全に十進数（Decimal）に変換し、四捨五入して整数（int）を返します。
    - カンマ、スペース、全角スペースを除去
    - 全角数字を半角数字に置換
    - Decimal による四捨五入 (ROUND_HALF_UP) を行い、整数化
    - パースできない場合は 0 を返します
    """
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    val_str = str(value).strip().translate(_TRANS_MAP)
    if not val_str:
        return 0

    try:
        return int(Decimal(val_str).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except Exception:
        return 0

