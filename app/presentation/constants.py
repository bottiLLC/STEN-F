from domain.models.account import AccountType

ACCOUNT_TYPE_JP = {
    AccountType.CURRENT_ASSET: "流動資産",
    AccountType.FIXED_ASSET: "固定資産",
    AccountType.DEFERRED_ASSET: "繰延資産",
    AccountType.CURRENT_LIABILITY: "流動負債",
    AccountType.FIXED_LIABILITY: "固定負債",
    AccountType.EQUITY: "純資産",
    AccountType.REVENUE: "売上",
    AccountType.COST_OF_SALES: "売上原価",
    AccountType.SGA: "販管費",
    AccountType.NON_OPERATING_INCOME: "営業外収益",
    AccountType.NON_OPERATING_EXPENSE: "営業外費用",
    AccountType.EXTRAORDINARY_INCOME: "特別利益",
    AccountType.EXTRAORDINARY_LOSS: "特別損失",
}

FY_STATUS_JP = {
    "OPEN": "進行中",
    "CLOSED": "確定済み"
}
