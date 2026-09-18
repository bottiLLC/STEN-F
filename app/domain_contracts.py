# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from enum import Enum
import re
from typing import Any, Final

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# --- 1. Datum Plane (Enums, Constants, and Schemas) ---
class AccountType(str, Enum):
    """Accounting classification category adhering to Japanese double-entry standards."""

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
        """Japanese localized display label for account classification."""
        labels: Final[dict[str, str]] = {
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
    def from_label(cls, label: str) -> AccountType:
        """Resolve AccountType enum variant from Japanese localized label.

        Args:
            label: Japanese accounting category name.

        Returns:
            Resolved AccountType enum member.

        Raises:
            ValueError: If label does not map to any known AccountType.
        """
        for t in cls:
            if t.label == label:
                return t
        raise ValueError(f"Unknown label: {label}")


_RAW_ACCOUNTS: Final[tuple[tuple[str, str, AccountType, str], ...]] = (
    ("1110", "現金", AccountType.CURRENT_ASSET, "手元の現金"),
    ("1120", "当座預金", AccountType.CURRENT_ASSET, "当座預金口座"),
    ("1130", "普通預金", AccountType.CURRENT_ASSET, "普通預金口座"),
    ("1140", "有価証券", AccountType.CURRENT_ASSET, "売買目的の有価証券"),
    ("1150", "仮払金", AccountType.CURRENT_ASSET, "使途不明の支出など"),
    ("1160", "前払費用", AccountType.CURRENT_ASSET, "継続的役務提供の前払い"),
    ("1170", "立替金", AccountType.CURRENT_ASSET, "他者負担分の立替払い"),
    ("1180", "未収入金", AccountType.CURRENT_ASSET, "本業以外の営業外未収金"),
    ("1190", "売掛金", AccountType.CURRENT_ASSET, "商品・サービスの掛け代金"),
    ("1510", "建物", AccountType.FIXED_ASSET, "事務所・店舗等の建物"),
    ("1520", "車両運搬具", AccountType.FIXED_ASSET, "営業車・トラックなど"),
    ("1530", "工具器具備品", AccountType.FIXED_ASSET, "PC・什器など（10万円以上）"),
    ("1540", "ソフトウェア", AccountType.FIXED_ASSET, "自社利用等の無形固定資産"),
    ("1710", "創立費", AccountType.DEFERRED_ASSET, "会社設立にかかった費用"),
    ("1720", "開業費", AccountType.DEFERRED_ASSET, "営業開始までにかかった費用"),
    ("2110", "買掛金", AccountType.CURRENT_LIABILITY, "仕入先への未払代金"),
    ("2120", "未払金", AccountType.CURRENT_LIABILITY, "固定資産購入や経費等の未払額"),
    ("2130", "未払費用", AccountType.CURRENT_LIABILITY, "継続的役務提供の未払分"),
    ("2140", "預り金", AccountType.CURRENT_LIABILITY, "源泉税・社保等の預り分"),
    ("2150", "短期借入金", AccountType.CURRENT_LIABILITY, "1年以内に返済予定の借入金"),
    (
        "2160",
        "未払法人税等",
        AccountType.CURRENT_LIABILITY,
        "確定申告納付予定の法人税等",
    ),
    ("2170", "前受金", AccountType.CURRENT_LIABILITY, "受注時の内金・前受け分"),
    ("2180", "仮受金", AccountType.CURRENT_LIABILITY, "内容未確定の入金"),
    ("2510", "長期借入金", AccountType.FIXED_LIABILITY, "返済期日が1年を超える借入金"),
    ("3110", "資本金", AccountType.EQUITY, "出資者から払い込まれた資金"),
    ("3120", "繰越利益剰余金", AccountType.EQUITY, "過年度からの累積利益"),
    ("4110", "売上高", AccountType.REVENUE, "本業のサービス・商品販売収入"),
    ("4120", "雑収入", AccountType.REVENUE, "本業に付随する少額の収入"),
    ("5110", "仕入高", AccountType.COST_OF_SALES, "販売商品の仕入費用"),
    ("5120", "外注費", AccountType.COST_OF_SALES, "外部への業務委託費用"),
    ("6110", "役員報酬", AccountType.SGA, "役員に対する報酬"),
    ("6120", "給料手当", AccountType.SGA, "従業員に対する給与・賞与"),
    ("6130", "法定福利費", AccountType.SGA, "健康保険・厚生年金の会社負担分"),
    ("6140", "福利厚生費", AccountType.SGA, "従業員のための慶弔費・飲食代等"),
    ("6150", "旅費交通費", AccountType.SGA, "電車代、バス代、出張旅費など"),
    ("6160", "通信費", AccountType.SGA, "電話代、インターネット代、切手代"),
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
)

DEFAULT_ACCOUNTS: Final[tuple[dict[str, Any], ...]] = tuple(
    {"code": c, "name": n, "type": t, "description": d} for c, n, t, d in _RAW_ACCOUNTS
)


class Account(BaseModel):
    """Chart of accounts entity representing a ledger account."""

    id: int | None = Field(None, description="Database ID")
    code: str = Field(..., min_length=1, max_length=10)
    name: str = Field(..., min_length=1)
    type: AccountType
    description: str | None = None

    @property
    def type_label(self) -> str:
        """Japanese localized label for account category."""
        return self.type.label

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class Corporation(BaseModel):
    """Tenant legal entity profile for financial reporting."""

    id: int | None = None
    name: str = ""
    address: str | None = None
    representative_title: str | None = None
    representative_name: str | None = None
    corporate_number: str | None = None
    invoice_number: str | None = None
    phone_number: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class Counterparty(BaseModel):
    """Vendor or customer entity for transaction indexing and T-number lookup."""

    id: int | None = None
    name: str
    name_kana: str | None = None
    reading: str | None = None
    invoice_number: str | None = Field(None, pattern=r"^T[0-9]{13}$")
    debit_account_id: int | None = None
    credit_account_id: int | None = None
    description_template: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @field_validator("invoice_number", mode="before")
    @classmethod
    def clean_invoice_number(cls, v: object) -> str | None:
        """Strip whitespace and normalize blank strings to None.

        Args:
            v: Input invoice number representation.

        Returns:
            Normalized registration number string or None.
        """
        if isinstance(v, str):
            v_stripped = v.strip()
            return v_stripped if v_stripped else None
        return None


class FiscalYear(BaseModel):
    """Accounting financial period definition."""

    id: int | None = Field(None, description="ID")
    name: str = Field(..., description="年度名 (例: 第10期)")
    start_date: date = Field(..., description="開始日")
    end_date: date = Field(..., description="終了日")
    status: str = Field("OPEN", description="ステータス (OPEN/CLOSED)")
    period_number: int | None = Field(None, description="期数 (数値)")
    created_at: datetime | None = Field(None, description="作成日時")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class Abstract(BaseModel):
    """Common transaction summary description snippet."""

    id: int | None = Field(None, description="ID")
    account_id: int = Field(..., description="紐づく勘定科目ID")
    text: str = Field(..., description="摘要内容")
    account_name: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class TransactionLine(BaseModel):
    """Single split leg of a double-entry journal entry."""

    id: int | None = None
    account_id: int
    debit: int = Field(default=0, ge=0)
    credit: int = Field(default=0, ge=0)
    account: Account | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @property
    def amount(self) -> int:
        """Effective absolute amount of this journal line."""
        return self.debit if self.debit > 0 else self.credit


class Transaction(BaseModel):
    """Double-entry balanced accounting journal transaction entry."""

    id: int | None = None
    date: date
    description: str
    lines: list[TransactionLine] = Field(default_factory=list)
    is_deleted: bool = False
    deleted_at: datetime | None = None
    counterparty: str | None = None
    invoice_number: str | None = Field(None, pattern=r"^T[0-9]{13}$")
    evidence_path: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @model_validator(mode="after")
    def check_balance(self) -> Transaction:
        """Verify strict debit and credit balance conservation.

        Returns:
            Validated Transaction instance.

        Raises:
            ValueError: If debit total does not strictly equal credit total.
        """
        total_debit = sum(line.debit for line in self.lines)
        total_credit = sum(line.credit for line in self.lines)
        if total_debit != total_credit:
            raise ValueError(
                f"Unbalanced Transaction: Debit({total_debit}) != Credit({total_credit})"
            )
        return self

    @field_validator("invoice_number", mode="before")
    @classmethod
    def clean_invoice_number(cls, v: object) -> str | None:
        """Sanitize invoice registration number string.

        Args:
            v: Input invoice number representation.

        Returns:
            Stripped string or None.
        """
        if isinstance(v, str):
            v_stripped = v.strip()
            return v_stripped if v_stripped else None
        return None


class TaxBreakdownItem(BaseModel):
    """Tax rate slice extracted from receipts."""

    tax_rate: str
    tax_amount: int | None = None
    amount_excl_tax: int | None = None
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ReceiptData(BaseModel):
    """Parsed structured data payload from OCR receipts."""

    merchant_name: str | None = None
    transaction_date: str | None = None
    total_amount_incl_tax: int | None = None
    invoice_registration_number: str | None = None
    tax_breakdown: list[TaxBreakdownItem] | None = None
    total_tax_amount: int | None = None
    total_amount_excl_tax: int | None = None
    confidence_score: float = 0.0
    needs_manual_review: bool = False
    is_registered_merchant: bool = False
    error_message: str | None = None
    inferred_debit_account_id: str | None = None
    inferred_credit_account_id: str | None = None
    description: str | None = None
    is_dictionary_matched: bool = False

    model_config = ConfigDict(from_attributes=True, extra="forbid")


Receipt = ReceiptData


class SystemSettings(BaseModel):
    """Global system configuration model stored in database."""

    id: int | None = Field(None, description="Database ID")
    ai_api_key: str | None = Field(None, description="Gemini API Key for AI operations")
    backup_path: str | None = Field(None, description="Database backup directory path")
    ai_model: str | None = Field(None, description="AI Model")

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class TrialBalanceRow(BaseModel):
    """Single row aggregated in the trial balance sheet."""

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
    """Grouped financial categories in trial balance or financial reports."""

    title: str
    rows: list[TrialBalanceRow] = []
    total: int = 0
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class FinancialReport(BaseModel):
    """Annual financial statement set (Balance Sheet & Profit and Loss)."""

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
def validate_invoice_number_format(number: str | None) -> bool:
    """Validate Qualified Invoice registration number syntax (T + 13 digits).

    Args:
        number: Candidate registration number string.

    Returns:
        True if matching official T-number format, False otherwise.
    """
    if not number:
        return False
    return bool(re.match(r"^T[0-9]{13}$", number.strip()))


# --- 3. Public Domain Interfaces ---
class IMasterRepository(ABC):
    """Abstract contract for master entity persistence and retrieval."""

    @abstractmethod
    async def get_system_settings(self) -> SystemSettings:
        """Fetch singleton system settings."""
        ...

    @abstractmethod
    async def save_system_settings(self, settings: SystemSettings) -> SystemSettings:
        """Persist or update system settings."""
        ...

    @abstractmethod
    async def get_corporation(self) -> Corporation | None:
        """Fetch tenant corporation profile."""
        ...

    @abstractmethod
    async def save_corporation(self, corp: Corporation) -> Corporation:
        """Persist or update corporation profile."""
        ...

    @abstractmethod
    async def get_fiscal_years(self) -> list[FiscalYear]:
        """List all defined fiscal years."""
        ...

    @abstractmethod
    async def get_fiscal_year(self, fy_id: int) -> FiscalYear | None:
        """Fetch specific fiscal year by ID."""
        ...

    @abstractmethod
    async def save_fiscal_year(self, fy: FiscalYear) -> FiscalYear:
        """Persist or update fiscal year."""
        ...

    @abstractmethod
    async def delete_fiscal_year(self, fy_id: int) -> bool:
        """Delete fiscal year by ID."""
        ...

    @abstractmethod
    async def get_counterparties(self) -> list[Counterparty]:
        """List all counterparties."""
        ...

    @abstractmethod
    async def save_counterparty(self, counterparty: Counterparty) -> Counterparty:
        """Persist or update counterparty."""
        ...

    @abstractmethod
    async def get_counterparty_by_keyword(self, keyword: str) -> Counterparty | None:
        """Find counterparty by exact or fuzzy name match."""
        ...

    @abstractmethod
    async def delete_counterparty(self, cp_id: int) -> bool:
        """Delete counterparty by ID."""
        ...

    @abstractmethod
    async def get_accounts(self) -> list[Account]:
        """List all chart of accounts."""
        ...

    @abstractmethod
    async def save_account(self, account: Account) -> Account:
        """Persist or update account."""
        ...

    @abstractmethod
    async def delete_account(self, account_id: int) -> bool:
        """Delete account by ID."""
        ...

    @abstractmethod
    async def get_abstracts(self) -> list[Abstract]:
        """List all predefined abstracts."""
        ...

    @abstractmethod
    async def save_abstract(self, abstract: Abstract) -> Abstract:
        """Persist or update abstract."""
        ...

    @abstractmethod
    async def delete_abstract(self, abs_id: int) -> bool:
        """Delete abstract by ID."""
        ...


class ILedgerRepository(ABC):
    """Abstract contract for double-entry bookkeeping ledger operations."""

    @abstractmethod
    async def get_accounts(self) -> list[Account]:
        """List all chart of accounts."""
        ...

    @abstractmethod
    async def get_transactions(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        include_deleted: bool = False,
        include_relationships: bool = False,
    ) -> list[Transaction]:
        """Query transactions matching date range and deletion flags."""
        ...

    @abstractmethod
    async def get_transactions_by_account(
        self,
        account_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
        include_deleted: bool = False,
    ) -> list[Transaction]:
        """Query transactions impacting specific account ID."""
        ...

    @abstractmethod
    async def add_transaction(self, transaction: Transaction) -> int:
        """Insert new double-entry transaction and return ID."""
        ...

    @abstractmethod
    async def has_transactions_for_account(self, account_id: int) -> bool:
        """Check whether any transaction references given account ID."""
        ...

    @abstractmethod
    async def delete_transaction(self, transaction_id: int) -> bool:
        """Logically mark transaction as deleted."""
        ...

    @abstractmethod
    async def get_trial_balance_data(self, fiscal_year_id: int) -> list[dict[str, Any]]:
        """Compute aggregated trial balance rows for fiscal period."""
        ...

    @abstractmethod
    async def commit(self) -> None:
        """Commit transaction unit of work."""
        ...

    @abstractmethod
    async def update_transaction(self, transaction: Transaction) -> bool:
        """Update existing transaction header and lines."""
        ...

    @abstractmethod
    async def update_evidence_path(self, transaction_id: int, path: str) -> bool:
        """Update storage file path of attached receipt evidence."""
        ...

    @abstractmethod
    async def get_frequent_account_ids(self, limit: int = 5) -> list[int]:
        """Fetch most frequently used debit/credit account IDs."""
        ...

    @abstractmethod
    async def get_fiscal_year(self, fiscal_year_id: int) -> FiscalYear | None:
        """Fetch fiscal year metadata."""
        ...
