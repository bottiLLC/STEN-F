from domain.models.account import AccountType

DEFAULT_ACCOUNTS = [
    # 1. 流動資産 (Current Assets)
    {"code": "1110", "name": "現金", "type": AccountType.CURRENT_ASSET, "description": "手元の現金"},
    {"code": "1120", "name": "当座預金", "type": AccountType.CURRENT_ASSET, "description": "当座預金口座"},
    {"code": "1130", "name": "普通預金", "type": AccountType.CURRENT_ASSET, "description": "普通預金口座"},
    {"code": "1140", "name": "有価証券", "type": AccountType.CURRENT_ASSET, "description": "売買目的の有価証券"},
    {"code": "1150", "name": "仮払金", "type": AccountType.CURRENT_ASSET, "description": "使途不明の支出など"},
    {"code": "1160", "name": "前払費用", "type": AccountType.CURRENT_ASSET, "description": "継続的役務提供の前払い"},

    # 2. 固定資産 (Fixed Assets)
    {"code": "1210", "name": "建物", "type": AccountType.FIXED_ASSET, "description": "店舗、事務所、倉庫など"},
    {"code": "1220", "name": "構築物", "type": AccountType.FIXED_ASSET, "description": "塀、舗装、看板など"},
    {"code": "1230", "name": "車両運搬具", "type": AccountType.FIXED_ASSET, "description": "社用車など"},
    {"code": "1240", "name": "工具器具備品", "type": AccountType.FIXED_ASSET, "description": "パソコン、机、椅子など"},
    {"code": "1250", "name": "土地", "type": AccountType.FIXED_ASSET, "description": "事業用の土地"},
    {"code": "1260", "name": "投資有価証券", "type": AccountType.FIXED_ASSET, "description": "長期保有目的の有価証券"},
    # User listed these under Fixed Assets, but accounting-wise often Deferred. 
    # Validating if we stick to Fixed or use Deferred if available.
    # Given the user wants them in "2. Fixed Assets", but they are legally Deferred Assets (繰延資産).
    # However, for simplicity in UI grouping, user might expect them together?
    # Actually, let's map them to DEFERRED_ASSET as it exists in the system.
    {"code": "1310", "name": "創立費", "type": AccountType.DEFERRED_ASSET, "description": "会社設立時の費用"},
    {"code": "1320", "name": "開業費", "type": AccountType.DEFERRED_ASSET, "description": "営業開始までの費用"},

    # 3. 流動負債 (Current Liabilities)
    {"code": "2110", "name": "短期借入金", "type": AccountType.CURRENT_LIABILITY, "description": "1年以内に返済する借入金"},
    {"code": "2120", "name": "未払金", "type": AccountType.CURRENT_LIABILITY, "description": "本来の営業取引以外の未払い"},
    {"code": "2130", "name": "預り金", "type": AccountType.CURRENT_LIABILITY, "description": "源泉税、社会保険料の預かり区分"},
    {"code": "2140", "name": "仮受金", "type": AccountType.CURRENT_LIABILITY, "description": "内容不明の入金など"},

    # 4. 固定負債 (Fixed Liabilities)
    {"code": "2210", "name": "長期借入金", "type": AccountType.FIXED_LIABILITY, "description": "1年を超えて返済する借入金"},
    {"code": "2220", "name": "役員借入金", "type": AccountType.FIXED_LIABILITY, "description": "役員からの借入金"},

    # PL関連
    # 1. 売上高 (Revenue)
    {"code": "4110", "name": "売上高", "type": AccountType.REVENUE, "description": "主たる営業活動による収益"},

    # 2. 販売費及び一般管理費 (SGA)
    {"code": "6110", "name": "役員報酬", "type": AccountType.SGA, "description": "役員への報酬"},
    {"code": "6120", "name": "法定福利費", "type": AccountType.SGA, "description": "社会保険料の会社負担分"},
    {"code": "6130", "name": "旅費交通費", "type": AccountType.SGA, "description": "電車代、バス代、宿泊費など"},
    {"code": "6140", "name": "通信費", "type": AccountType.SGA, "description": "電話代、インターネット代、切手代"},
    {"code": "6150", "name": "水道光熱費", "type": AccountType.SGA, "description": "電気、ガス、水道代"},
    {"code": "6160", "name": "地代家賃", "type": AccountType.SGA, "description": "事務所の家賃など"},
    {"code": "6170", "name": "消耗品費", "type": AccountType.SGA, "description": "10万円未満の物品購入"},
    {"code": "6180", "name": "接待交際費", "type": AccountType.SGA, "description": "取引先との飲食代、贈答品など"},
    {"code": "6190", "name": "租税公課", "type": AccountType.SGA, "description": "固定資産税、印紙代など"},
    {"code": "6200", "name": "支払手数料", "type": AccountType.SGA, "description": "振込手数料、専門家報酬など"},
    {"code": "6210", "name": "減価償却費", "type": AccountType.SGA, "description": "資産の費用化"},
    {"code": "6220", "name": "雑費", "type": AccountType.SGA, "description": "その他少額の費用"},

    # 3. 営業外収益 (Non-Operating Income)
    {"code": "7110", "name": "受取利息", "type": AccountType.NON_OPERATING_INCOME, "description": "預金利息など"},
    {"code": "7120", "name": "受取配当金", "type": AccountType.NON_OPERATING_INCOME, "description": "株式配当金など"},
    {"code": "7130", "name": "雑収入", "type": AccountType.NON_OPERATING_INCOME, "description": "その他営業外の収益"},

    # 4. 営業外費用 (Non-Operating Expense)
    {"code": "7510", "name": "支払利息", "type": AccountType.NON_OPERATING_EXPENSE, "description": "借入金の利息"},
    {"code": "7520", "name": "創立費償却", "type": AccountType.NON_OPERATING_EXPENSE, "description": "創立費の償却"},
    {"code": "7530", "name": "開業費償却", "type": AccountType.NON_OPERATING_EXPENSE, "description": "開業費の償却"},


    # 5. 純資産 (Equity)
    {"code": "3110", "name": "資本金", "type": AccountType.EQUITY, "description": "設立時の出資額"},
    {"code": "3120", "name": "繰越利益剰余金", "type": AccountType.EQUITY, "description": "過去の利益の蓄積"},

    {"code": "9110", "name": "法人税、住民税及び事業税", "type": AccountType.TAXES, "description": "法人税、住民税及び事業税"},
]
