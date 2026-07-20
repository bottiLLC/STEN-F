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

import structlog
from app.domain.models.account import Account, AccountType

log = structlog.get_logger()

DEFAULT_ACCOUNTS = [
    # Assets (資産)
    {
        "code": "1110",
        "name": "現金",
        "type": AccountType.CURRENT_ASSET,
        "description": "手許にある現金",
    },
    {
        "code": "1120",
        "name": "小口現金",
        "type": AccountType.CURRENT_ASSET,
        "description": "定額資金前渡法などで管理する現金",
    },
    {
        "code": "1130",
        "name": "普通預金",
        "type": AccountType.CURRENT_ASSET,
        "description": "銀行の普通預金口座",
    },
    {
        "code": "1140",
        "name": "当座預金",
        "type": AccountType.CURRENT_ASSET,
        "description": "小切手支払などが可能な預金",
    },
    {
        "code": "1150",
        "name": "受取手形",
        "type": AccountType.CURRENT_ASSET,
        "description": "商品販売等で受け取った手形",
    },
    {
        "code": "1160",
        "name": "売掛金",
        "type": AccountType.CURRENT_ASSET,
        "description": "掛けで販売した代金の未回収分",
    },
    {
        "code": "1170",
        "name": "棚卸資産",
        "type": AccountType.CURRENT_ASSET,
        "description": "商品、製品、原材料などの在庫",
    },
    {
        "code": "1180",
        "name": "前払費用",
        "type": AccountType.CURRENT_ASSET,
        "description": "継続的役務提供契約で前払いした費用",
    },
    {
        "code": "1210",
        "name": "建物",
        "type": AccountType.FIXED_ASSET,
        "description": "店舗、倉庫、事務所などの建物",
    },
    {
        "code": "1220",
        "name": "備品",
        "type": AccountType.FIXED_ASSET,
        "description": "パソコン、机、椅子などの事務機器",
    },
    # Liabilities (負債)
    {
        "code": "2110",
        "name": "支払手形",
        "type": AccountType.CURRENT_LIABILITY,
        "description": "商品の購入等で振り出した手形",
    },
    {
        "code": "2120",
        "name": "買掛金",
        "type": AccountType.CURRENT_LIABILITY,
        "description": "掛けで購入した代金の未払分",
    },
    {
        "code": "2130",
        "name": "短期借入金",
        "type": AccountType.CURRENT_LIABILITY,
        "description": "1年以内に返済期限が到来する借入金",
    },
    {
        "code": "2140",
        "name": "未払金",
        "type": AccountType.CURRENT_LIABILITY,
        "description": "本来の営業取引以外の未払代金",
    },
    {
        "code": "2150",
        "name": "預り金",
        "type": AccountType.CURRENT_LIABILITY,
        "description": "源泉所得税、社会保険料などの預り分",
    },
    {
        "code": "2160",
        "name": "未払法人税等",
        "type": AccountType.CURRENT_LIABILITY,
        "description": "決算により確定した未払いの法人税等",
    },
    {
        "code": "2210",
        "name": "長期借入金",
        "type": AccountType.FIXED_LIABILITY,
        "description": "返済期限が1年を超える借入金",
    },
    {
        "code": "2220",
        "name": "役員借入金",
        "type": AccountType.FIXED_LIABILITY,
        "description": "役員からの借入金",
    },
    # Equity (純資産)
    {
        "code": "3110",
        "name": "資本金",
        "type": AccountType.EQUITY,
        "description": "会社設立時等の出資額",
    },
    {
        "code": "3120",
        "name": "繰越利益剰余金",
        "type": AccountType.EQUITY,
        "description": "過年度からの利益の蓄積",
    },
    # Revenue (収益)
    {
        "code": "4110",
        "name": "売上高",
        "type": AccountType.REVENUE,
        "description": "商品・サービスの販売による収益",
    },
    {
        "code": "4210",
        "name": "受取利息",
        "type": AccountType.NON_OPERATING_INCOME,
        "description": "預貯金などの利息",
    },
    {
        "code": "4220",
        "name": "雑収入",
        "type": AccountType.NON_OPERATING_INCOME,
        "description": "本業以外の重要性の低い収益",
    },
    # Expenses (費用) - Cost of Sales
    {
        "code": "5110",
        "name": "仕入高",
        "type": AccountType.COST_OF_SALES,
        "description": "商品の仕入原価",
    },
    {
        "code": "5120",
        "name": "外注費",
        "type": AccountType.COST_OF_SALES,
        "description": "業務委託費など",
    },
    # Expenses (費用) - SGA
    {
        "code": "6110",
        "name": "役員報酬",
        "type": AccountType.SGA,
        "description": "取締役などの報酬",
    },
    {
        "code": "6120",
        "name": "給料手当",
        "type": AccountType.SGA,
        "description": "従業員の給与・手当",
    },
    {
        "code": "6130",
        "name": "法定福利費",
        "type": AccountType.SGA,
        "description": "社会保険料の会社負担分",
    },
    {
        "code": "6210",
        "name": "広告宣伝費",
        "type": AccountType.SGA,
        "description": "広告、チラシ、Web広報費など",
    },
    {
        "code": "6220",
        "name": "旅費交通費",
        "type": AccountType.SGA,
        "description": "電車、バス、タクシー、宿泊費",
    },
    {
        "code": "6230",
        "name": "通信費",
        "type": AccountType.SGA,
        "description": "電話、インターネット、郵便代",
    },
    {
        "code": "6240",
        "name": "消耗品費",
        "type": AccountType.SGA,
        "description": "10万円未満の物品購入費",
    },
    {
        "code": "6250",
        "name": "接待交際費",
        "type": AccountType.SGA,
        "description": "取引先との飲食等の費用",
    },
    {
        "code": "6260",
        "name": "地代家賃",
        "type": AccountType.SGA,
        "description": "事務所の家賃、駐車場代",
    },
    {
        "code": "6270",
        "name": "水道光熱費",
        "type": AccountType.SGA,
        "description": "電気、ガス、水道代",
    },
    {
        "code": "6280",
        "name": "租税公課",
        "type": AccountType.SGA,
        "description": "印紙税、固定資産税など",
    },
    {
        "code": "6290",
        "name": "支払手数料",
        "type": AccountType.SGA,
        "description": "振込手数料、専門家報酬など",
    },
    {
        "code": "6310",
        "name": "雑費",
        "type": AccountType.SGA,
        "description": "他の科目に当てはまらない少額費用",
    },
    # Expenses (費用) - Non-Operating
    {
        "code": "7110",
        "name": "支払利息",
        "type": AccountType.NON_OPERATING_EXPENSE,
        "description": "借入金の利息",
    },
]


async def seed_accounts_with_service(service):
    """Seed default accounts using the provided master service."""
    existing = await service.get_accounts()
    existing_codes = {acc.code for acc in existing}

    added_count = 0
    for acc_data in DEFAULT_ACCOUNTS:
        if acc_data["code"] not in existing_codes:
            acc = Account(**acc_data)
            await service.save_account(acc)
            added_count += 1

    if added_count > 0:
        log.info("Default accounts synced", added_count=added_count)


async def seed_accounts():
    """Seed existing database with default accounts if empty, or sync missing ones."""
    # Ensure tables exist
    from app.infrastructure.db.session import init_db

    await init_db()

    # To avoid ORM model import issues without looking at files, let's use the MasterService via DI
    # But DI might need loop.
    from app.ui.di import DI

    async with DI.get_master_service() as service:
        await seed_accounts_with_service(service)
