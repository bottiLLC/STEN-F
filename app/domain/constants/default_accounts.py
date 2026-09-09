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

from app.domain.models.account import AccountType

_RAW_ACCOUNTS = [
    # 流動資産
    ("1110", "現金", AccountType.CURRENT_ASSET, "手元の現金"),
    ("1120", "当座預金", AccountType.CURRENT_ASSET, "当座預金口座"),
    ("1130", "普通預金", AccountType.CURRENT_ASSET, "普通預金口座"),
    ("1140", "有価証券", AccountType.CURRENT_ASSET, "売買目的の有価証券"),
    ("1150", "仮払金", AccountType.CURRENT_ASSET, "使途不明の支出など"),
    ("1160", "前払費用", AccountType.CURRENT_ASSET, "継続的役務提供の前払い"),
    # 固定資産
    ("1210", "建物", AccountType.FIXED_ASSET, "店舗、事務所、倉庫など"),
    ("1220", "構築物", AccountType.FIXED_ASSET, "塀、舗装、看板など"),
    ("1230", "車両運搬具", AccountType.FIXED_ASSET, "社用車など"),
    ("1240", "工具器具備品", AccountType.FIXED_ASSET, "パソコン、机、椅子など"),
    ("1250", "土地", AccountType.FIXED_ASSET, "事業用の土地"),
    ("1260", "投資有価証券", AccountType.FIXED_ASSET, "長期保有目的の有価証券"),
    # 繰延資産
    ("1310", "創立費", AccountType.DEFERRED_ASSET, "会社設立時の費用"),
    ("1320", "開業費", AccountType.DEFERRED_ASSET, "営業開始までの費用"),
    # 流動負債
    ("2110", "短期借入金", AccountType.CURRENT_LIABILITY, "1年以内に返済する借入金"),
    ("2120", "未払金", AccountType.CURRENT_LIABILITY, "本来の営業取引以外の未払い"),
    ("2130", "預り金", AccountType.CURRENT_LIABILITY, "源泉税、社会保険料の預かり区分"),
    ("2140", "仮受金", AccountType.CURRENT_LIABILITY, "内容不明の入金など"),
    (
        "2150",
        "未払法人税等",
        AccountType.CURRENT_LIABILITY,
        "決算により確定した未払いの法人税等",
    ),
    # 固定負債
    ("2210", "長期借入金", AccountType.FIXED_LIABILITY, "1年を超えて返済する借入金"),
    ("2220", "役員借入金", AccountType.FIXED_LIABILITY, "役員からの借入金"),
    # 純資産
    ("3110", "資本金", AccountType.EQUITY, "設立時の出資額"),
    ("3120", "繰越利益剰余金", AccountType.EQUITY, "過去の利益の蓄積"),
    # 売上高
    ("4110", "売上高", AccountType.REVENUE, "主たる営業活動による収益"),
    # 販管費
    ("6110", "役員報酬", AccountType.SGA, "役員への報酬"),
    ("6120", "法定福利費", AccountType.SGA, "社会保険料の会社負担分"),
    ("6130", "旅費交通費", AccountType.SGA, "電車代、バス代、宿泊費など"),
    ("6140", "通信費", AccountType.SGA, "電話代、インターネット代、切手代"),
    ("6150", "水道光熱費", AccountType.SGA, "電気、ガス、水道代"),
    ("6160", "地代家賃", AccountType.SGA, "事務所の家賃など"),
    ("6170", "消耗品費", AccountType.SGA, "10万円未満の物品購入"),
    ("6180", "接待交際費", AccountType.SGA, "取引先との飲食代、贈答品など"),
    ("6190", "租税公課", AccountType.SGA, "固定資産税、印紙代など"),
    ("6200", "支払手数料", AccountType.SGA, "振込手数料、専門家報酬など"),
    ("6210", "減価償却費", AccountType.SGA, "資産の費用化"),
    ("6220", "雑費", AccountType.SGA, "その他少額の費用"),
    # 営業外収益
    ("7110", "受取利息", AccountType.NON_OPERATING_INCOME, "預金利息など"),
    ("7120", "受取配当金", AccountType.NON_OPERATING_INCOME, "株式配当金など"),
    ("7130", "雑収入", AccountType.NON_OPERATING_INCOME, "その他営業外の収益"),
    # 営業外費用
    ("7510", "支払利息", AccountType.NON_OPERATING_EXPENSE, "借入金の利息"),
    ("7520", "創立費償却", AccountType.NON_OPERATING_EXPENSE, "創立費の償却"),
    ("7530", "開業費償却", AccountType.NON_OPERATING_EXPENSE, "開業費の償却"),
    # 税金
    ("9110", "法人税、住民税及び事業税", AccountType.TAXES, "法人税、住民税及び事業税"),
]

DEFAULT_ACCOUNTS = [
    {"code": c, "name": n, "type": t, "description": d} for c, n, t, d in _RAW_ACCOUNTS
]
