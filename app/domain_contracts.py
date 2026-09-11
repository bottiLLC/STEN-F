# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from abc import ABC, abstractmethod
from datetime import date, datetime
from enum import Enum
import re
from typing import Any, Dict, List, Optional
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


# --- 1. Datum Plane (Enums, Constants, and Schemas) ---
class AccountType(str, Enum):
    CURRENT_ASSET = "CurrentAsset"
    FIXED_ASSET = "FixedAsset"
    DEFERRED_ASSET = "DeferredAsset"
    CURRENT_LIABILITY = "CurrentLiability"
    FIXED_LIABILITY = "FixedLiability"
    EQUITY = "Equity"
    REVENUE = "Revenue"
    COST_OF_SALES = "CostOfSales"
    SGA = "SGA"
    NON_OPERATING_INCOME = "NonOperatingIncome"
    NON_OPERATING_EXPENSE = "NonOperatingExpense"
    EXTRAORDINARY_INCOME = "ExtraordinaryIncome"
    EXTRAORDINARY_LOSS = "ExtraordinaryLoss"
    TAXES = "Taxes"

    @property
    def label(self) -> str:
        labels = {
            "CurrentAsset": "流動資産",
            "FixedAsset": "固定資産",
            "DeferredAsset": "繰延資産",
            "CurrentLiability": "流動負債",
            "FixedLiability": "固定負債",
            "Equity": "純資産",
            "Revenue": "売上高",
            "CostOfSales": "売上原価",
            "SGA": "販管費",
            "NonOperatingIncome": "営業外収益",
            "NonOperatingExpense": "営業外費用",
            "ExtraordinaryIncome": "特別利益",
            "ExtraordinaryLoss": "特別損失",
            "Taxes": "法人税等",
        }
        return labels.get(self.value, self.value)

    @classmethod
    def from_label(cls, label: str) -> "AccountType":
        for t in cls:
            if t.label == label:
                return t
        raise ValueError(f"Unknown label: {label}")


_RAW_ACCOUNTS = [
    ("1110", "現金", AccountType.CURRENT_ASSET, "手元の現金"),
    ("1120", "当座預金", AccountType.CURRENT_ASSET, "当座預金口座"),
    ("1130", "普通預金", AccountType.CURRENT_ASSET, "普通預金口座"),
    ("1140", "有価証券", AccountType.CURRENT_ASSET, "売買目的の有価証券"),
    ("1150", "仮払金", AccountType.CURRENT_ASSET, "使途不明の支出など"),
    ("1160", "前払費用", AccountType.CURRENT_ASSET, "継続的役務提供の前払い"),
    ("1210", "建物", AccountType.FIXED_ASSET, "店舗、事務所、倉庫など"),
    ("1220", "構築物", AccountType.FIXED_ASSET, "塀、舗装、看板など"),
    ("1230", "車両運搬具", AccountType.FIXED_ASSET, "社用車など"),
    ("1240", "工具器具備品", AccountType.FIXED_ASSET, "パソコン、机、椅子など"),
    ("1250", "土地", AccountType.FIXED_ASSET, "事業用の土地"),
    ("1260", "投資有価証券", AccountType.FIXED_ASSET, "長期保有目的の有価証券"),
    ("1310", "創立費", AccountType.DEFERRED_ASSET, "会社設立時の費用"),
    ("1320", "開業費", AccountType.DEFERRED_ASSET, "営業開始までの費用"),
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
    ("2210", "長期借入金", AccountType.FIXED_LIABILITY, "1年を超えて返済する借入金"),
    ("2220", "役員借入金", AccountType.FIXED_LIABILITY, "役員からの借入金"),
    ("3110", "資本金", AccountType.EQUITY, "設立時の出資額"),
    ("3120", "繰越利益剰余金", AccountType.EQUITY, "過去の利益の蓄積"),
    ("4110", "売上高", AccountType.REVENUE, "主たる営業活動による収益"),
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
    ("7110", "受取利息", AccountType.NON_OPERATING_INCOME, "預金利息など"),
    ("7120", "受取配当金", AccountType.NON_OPERATING_INCOME, "株式配当金など"),
    ("7130", "雑収入", AccountType.NON_OPERATING_INCOME, "その他営業外の収益"),
    ("7510", "支払利息", AccountType.NON_OPERATING_EXPENSE, "借入金の利息"),
    ("7520", "創立費償却", AccountType.NON_OPERATING_EXPENSE, "創立費の償却"),
    ("7530", "開業費償却", AccountType.NON_OPERATING_EXPENSE, "開業費の償却"),
    ("9110", "法人税、住民税及び事業税", AccountType.TAXES, "法人税、住民税及び事業税"),
]

DEFAULT_ACCOUNTS = [
    {"code": c, "name": n, "type": t, "description": d} for c, n, t, d in _RAW_ACCOUNTS
]


class Account(BaseModel):
    id: Optional[int] = Field(None, description="Database ID")
    code: str = Field(..., min_length=1, max_length=10)
    name: str = Field(..., min_length=1)
    type: AccountType
    description: Optional[str] = None

    @computed_field
    def type_label(self) -> str:
        return self.type.label

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class Corporation(BaseModel):
    id: Optional[int] = None
    name: str = ""
    address: Optional[str] = None
    representative_title: Optional[str] = None
    representative_name: Optional[str] = None
    corporate_number: Optional[str] = None
    invoice_number: Optional[str] = None
    phone_number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class Counterparty(BaseModel):
    id: Optional[int] = None
    name: str
    name_kana: Optional[str] = None
    reading: Optional[str] = None
    invoice_number: Optional[str] = Field(None, pattern=r"^T[0-9]{13}$")
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


class FiscalYear(BaseModel):
    id: Optional[int] = Field(None, description="ID")
    name: str = Field(..., description="年度名 (例: 第10期)")
    start_date: date = Field(..., description="開始日")
    end_date: date = Field(..., description="終了日")
    status: str = Field("OPEN", description="ステータス (OPEN/CLOSED)")
    period_number: Optional[int] = Field(None, description="期数 (数値)")
    created_at: Optional[datetime] = Field(None, description="作成日時")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class Abstract(BaseModel):
    id: Optional[int] = Field(None, description="ID")
    account_id: int = Field(..., description="紐づく勘定科目ID")
    text: str = Field(..., description="摘要内容")
    account_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class TransactionLine(BaseModel):
    id: Optional[int] = None
    account_id: int
    debit: int = Field(default=0, ge=0)
    credit: int = Field(default=0, ge=0)
    account: Optional[Account] = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @property
    def amount(self) -> int:
        return self.debit if self.debit > 0 else self.credit


class Transaction(BaseModel):
    id: Optional[int] = None
    date: date
    description: str
    lines: List[TransactionLine] = Field(default_factory=list)
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    counterparty: Optional[str] = None
    invoice_number: Optional[str] = Field(None, pattern=r"^T[0-9]{13}$")
    evidence_path: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @model_validator(mode="after")
    def check_balance(self) -> "Transaction":
        total_debit = sum(line.debit for line in self.lines)
        total_credit = sum(line.credit for line in self.lines)
        if total_debit != total_credit:
            raise ValueError(
                f"Unbalanced Transaction: Debit({total_debit}) != Credit({total_credit})"
            )
        return self

    @field_validator("invoice_number", mode="before")
    @classmethod
    def clean_invoice_number(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            v_stripped = v.strip()
            return v_stripped if v_stripped else None
        return v


class TaxBreakdownItem(BaseModel):
    tax_rate: str
    tax_amount: Optional[int] = None
    amount_excl_tax: Optional[int] = None
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ReceiptData(BaseModel):
    merchant_name: Optional[str] = None
    transaction_date: Optional[str] = None
    total_amount_incl_tax: Optional[int] = None
    invoice_registration_number: Optional[str] = None
    tax_breakdown: Optional[List[TaxBreakdownItem]] = None
    total_tax_amount: Optional[int] = None
    total_amount_excl_tax: Optional[int] = None
    confidence_score: float = 0.0
    needs_manual_review: bool = False
    is_registered_merchant: bool = False
    error_message: Optional[str] = None
    inferred_debit_account_id: Optional[str] = None
    inferred_credit_account_id: Optional[str] = None
    description: Optional[str] = None
    is_dictionary_matched: bool = False

    model_config = ConfigDict(from_attributes=True, extra="forbid")


Receipt = ReceiptData


class SystemSettings(BaseModel):
    id: Optional[int] = Field(None, description="Database ID")
    ai_api_key: Optional[str] = Field(
        None, description="Gemini API Key for AI operations"
    )
    backup_path: Optional[str] = Field(
        None, description="Database backup directory path"
    )
    ai_model: Optional[str] = Field(None, description="AI Model")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class TrialBalanceRow(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    account_type: AccountType
    debit_total: int = 0
    credit_total: int = 0
    balance: int = 0
    debit_balance: int = 0
    credit_balance: int = 0
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class FinancialSection(BaseModel):
    title: str
    rows: List[TrialBalanceRow] = []
    total: int = 0
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class FinancialReport(BaseModel):
    fiscal_year: FiscalYear
    current_assets: FinancialSection
    fixed_assets: FinancialSection
    deferred_assets: FinancialSection
    current_liabilities: FinancialSection
    fixed_liabilities: FinancialSection
    equity: FinancialSection
    revenue: FinancialSection
    cost_of_sales: FinancialSection
    sga: FinancialSection
    non_op_income: FinancialSection
    non_op_expense: FinancialSection
    extra_income: FinancialSection
    extra_loss: FinancialSection
    total_assets: int = 0
    total_liabilities: int = 0
    total_equity: int = 0
    gross_profit: int = 0
    operating_income: int = 0
    ordinary_income: int = 0
    income_before_tax: int = 0
    net_income: int = 0
    model_config = ConfigDict(from_attributes=True, extra="forbid")


# --- 2. Internal Pure Transformations ---
def validate_invoice_number_format(number: Optional[str]) -> bool:
    """Validate Qualified Invoice registration number syntax (T + 13 digits)."""
    if not number:
        return False
    return bool(re.match(r"^T[0-9]{13}$", number.strip()))


# --- 3. Public Domain Interfaces ---
class IMasterRepository(ABC):
    """Abstract contract for master entity persistence and retrieval."""

    @abstractmethod
    async def get_system_settings(self) -> SystemSettings: ...
    @abstractmethod
    async def save_system_settings(
        self, settings: SystemSettings
    ) -> SystemSettings: ...
    @abstractmethod
    async def get_corporation(self) -> Optional[Corporation]: ...
    @abstractmethod
    async def save_corporation(self, corp: Corporation) -> Corporation: ...
    @abstractmethod
    async def get_fiscal_years(self) -> List[FiscalYear]: ...
    @abstractmethod
    async def get_fiscal_year(self, fy_id: int) -> Optional[FiscalYear]: ...
    @abstractmethod
    async def save_fiscal_year(self, fy: FiscalYear) -> FiscalYear: ...
    @abstractmethod
    async def delete_fiscal_year(self, fy_id: int) -> bool: ...
    @abstractmethod
    async def get_counterparties(self) -> List[Counterparty]: ...
    @abstractmethod
    async def save_counterparty(self, counterparty: Counterparty) -> Counterparty: ...
    @abstractmethod
    async def get_counterparty_by_keyword(
        self, keyword: str
    ) -> Optional[Counterparty]: ...
    @abstractmethod
    async def delete_counterparty(self, cp_id: int) -> bool: ...
    @abstractmethod
    async def get_accounts(self) -> List[Account]: ...
    @abstractmethod
    async def save_account(self, account: Account) -> Account: ...
    @abstractmethod
    async def delete_account(self, account_id: int) -> bool: ...
    @abstractmethod
    async def get_abstracts(self) -> List[Abstract]: ...
    @abstractmethod
    async def save_abstract(self, abstract: Abstract) -> Abstract: ...
    @abstractmethod
    async def delete_abstract(self, abs_id: int) -> bool: ...


class ILedgerRepository(ABC):
    """Abstract contract for double-entry bookkeeping ledger operations."""

    @abstractmethod
    async def get_accounts(self) -> List[Account]: ...
    @abstractmethod
    async def get_transactions(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_deleted: bool = False,
        include_relationships: bool = False,
    ) -> List[Transaction]: ...
    @abstractmethod
    async def get_transactions_by_account(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_deleted: bool = False,
    ) -> List[Transaction]: ...
    @abstractmethod
    async def add_transaction(self, transaction: Transaction) -> int: ...
    @abstractmethod
    async def has_transactions_for_account(self, account_id: int) -> bool: ...
    @abstractmethod
    async def delete_transaction(self, transaction_id: int) -> bool: ...
    @abstractmethod
    async def get_trial_balance_data(
        self, fiscal_year_id: int
    ) -> List[Dict[str, Any]]: ...
    @abstractmethod
    async def commit(self) -> None: ...
    @abstractmethod
    async def update_transaction(self, transaction: Transaction) -> bool: ...
    @abstractmethod
    async def update_evidence_path(self, transaction_id: int, path: str) -> bool: ...
    @abstractmethod
    async def get_frequent_account_ids(self, limit: int = 5) -> List[int]: ...
    @abstractmethod
    async def get_fiscal_year(self, fiscal_year_id: int) -> Optional[FiscalYear]: ...


# --- 4. Self-Contained Smoke Harness ---
if __name__ == "__main__":
    acc = Account(code="1110", name="現金", type=AccountType.CURRENT_ASSET)
    assert acc.type_label == "流動資産"
    tx = Transaction(
        date=date.today(),
        description="Smoke Harness Journal Entry",
        lines=[
            TransactionLine(account_id=1, debit=1000, credit=0),
            TransactionLine(account_id=2, debit=0, credit=1000),
        ],
    )
    assert tx.lines[0].amount == 1000
    assert validate_invoice_number_format("T1234567890123") is True
    assert validate_invoice_number_format("invalid") is False
    assert len(DEFAULT_ACCOUNTS) > 20
