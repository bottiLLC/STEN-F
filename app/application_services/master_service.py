# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

from typing import Final

from app.domain_contracts import (
    Abstract,
    Account,
    Corporation,
    Counterparty,
    FiscalYear,
    ILedgerRepository,
    IMasterRepository,
    SystemSettings,
)

_LEGAL_ENTITY_KANA: Final[tuple[str, ...]] = (
    "カブシキガイシャ",
    "カブシキカイシャ",
    "カ）",
    "（カ",
    "ユウゲンガイシャ",
    "ユウゲンカイシャ",
    "ユ）",
    "（ユ",
    "ゴウドウガイシャ",
    "ド）",
    "（ド",
    "イッパンシャダンホウジン",
    "コウエキシャダンホウジン",
    "ガッコウホウジン",
    "シュウキョウホウジン",
    "イリョウホウジン",
    "シャカイフクシホウジン",
    "トクテイヒエイリカツドウホウジン",
    "　",
    " ",
)


def _clean_counterparty_sort_key(cp: Counterparty) -> str:
    """Normalize corporate legal suffix kana to derive alphabetical sorting key.

    Args:
        cp: Counterparty domain model.

    Returns:
        Cleansed kana or name string suitable for sorting.
    """
    key = str(cp.name_kana or cp.trade_name or cp.name or "")
    for token in _LEGAL_ENTITY_KANA:
        key = key.replace(token, "")
    return key


class MasterService:
    """Business service governing master catalog entities and configurations."""

    def __init__(
        self,
        repository: IMasterRepository,
        ledger_repository: ILedgerRepository | None = None,
    ) -> None:
        """Initialize service dependencies.

        Args:
            repository: Implementation of IMasterRepository.
            ledger_repository: Optional implementation of ILedgerRepository.
        """
        self.repository = repository
        self.ledger_repository = ledger_repository

    async def get_system_settings(self) -> SystemSettings:
        """Fetch system-wide settings.

        Returns:
            SystemSettings domain model.
        """
        return await self.repository.get_system_settings()

    async def save_system_settings(self, settings: SystemSettings) -> SystemSettings:
        """Persist modified system settings.

        Args:
            settings: Updated SystemSettings domain model.

        Returns:
            Saved SystemSettings instance.
        """
        return await self.repository.save_system_settings(settings)

    async def get_corporation(self) -> Corporation | None:
        """Fetch corporate identification details.

        Returns:
            Corporation profile or None.
        """
        return await self.repository.get_corporation()

    async def save_corporation(self, corp: Corporation) -> None:
        """Persist corporate identification details.

        Args:
            corp: Corporation domain model.
        """
        await self.repository.save_corporation(corp)

    async def get_fiscal_years(self) -> list[FiscalYear]:
        """Fetch all fiscal year periods.

        Returns:
            List of FiscalYear domain models.
        """
        return await self.repository.get_fiscal_years()

    async def get_fiscal_year_by_id(self, fy_id: int) -> FiscalYear | None:
        """Fetch single fiscal year period by identifier.

        Args:
            fy_id: Target fiscal year identifier.

        Returns:
            FiscalYear domain model or None.
        """
        return await self.repository.get_fiscal_year(fy_id)

    async def save_fiscal_year(self, fy: FiscalYear) -> FiscalYear:
        """Save fiscal year period boundary with non-overlapping period validation.

        Args:
            fy: FiscalYear domain model.

        Returns:
            Persisted FiscalYear instance.

        Raises:
            ValueError: If the period boundaries overlap with an existing fiscal year.
        """
        existing = await self.repository.get_fiscal_years()
        for ex in existing:
            if ex.id != fy.id and max(fy.start_date, ex.start_date) <= min(
                fy.end_date, ex.end_date
            ):
                raise ValueError(
                    f"会計年度の期間が既存の年度「{ex.name}」({ex.start_date}〜{ex.end_date}) と重複しています。"
                )
        return await self.repository.save_fiscal_year(fy)

    async def delete_fiscal_year(self, fy_id: int) -> None:
        """Remove unused open fiscal year record.

        Args:
            fy_id: Target fiscal year identifier.

        Raises:
            ValueError: If fiscal year is closed or contains journal entries.
        """
        target_fy = await self.repository.get_fiscal_year(fy_id)
        if target_fy:
            if target_fy.status == "CLOSED":
                raise ValueError("締め済みの会計年度は削除できません。")
            if self.ledger_repository:
                existing_txs = await self.ledger_repository.get_transactions(
                    start_date=target_fy.start_date,
                    end_date=target_fy.end_date,
                    include_deleted=True,
                )
                if existing_txs:
                    raise ValueError("仕訳が存在する会計年度は削除できません。")
        await self.repository.delete_fiscal_year(fy_id)

    async def get_accounts(self) -> list[Account]:
        """Retrieve full account catalog.

        Returns:
            List of Account domain models.
        """
        return await self.repository.get_accounts()

    async def save_account(self, account: Account) -> Account:
        """Save account definition enforcing unique account code.

        Args:
            account: Account domain model.

        Returns:
            Persisted Account instance.

        Raises:
            ValueError: If an account with the same code already exists.
        """
        existing = await self.repository.get_accounts()
        if any(a.code == account.code and a.id != account.id for a in existing):
            raise ValueError(
                f"勘定科目コード '{account.code}' は既に使用されています。"
            )
        return await self.repository.save_account(account)

    async def delete_account(self, account_id: int) -> None:
        """Delete unused account with transaction usage check.

        Args:
            account_id: Target account identifier.

        Raises:
            ValueError: If account has associated transactions.
        """
        if (
            self.ledger_repository
            and await self.ledger_repository.has_transactions_for_account(account_id)
        ):
            raise ValueError("この勘定科目は仕訳で使用されているため削除できません。")
        await self.repository.delete_account(account_id)

    async def get_abstracts(self) -> list[Abstract]:
        """Fetch all predefined transaction abstracts.

        Returns:
            List of Abstract domain models.
        """
        return await self.repository.get_abstracts()

    async def save_abstract(self, abstract: Abstract) -> Abstract:
        """Persist transaction abstract template.

        Args:
            abstract: Abstract domain model.

        Returns:
            Persisted Abstract instance.
        """
        return await self.repository.save_abstract(abstract)

    async def delete_abstract(self, abstract_id: int) -> None:
        """Delete transaction abstract template.

        Args:
            abstract_id: Target abstract identifier.
        """
        await self.repository.delete_abstract(abstract_id)

    async def get_counterparties(self) -> list[Counterparty]:
        """Retrieve sorted list of registered business counterparties.

        Returns:
            Sorted list of Counterparty domain models.
        """
        cps = await self.repository.get_counterparties()
        cps.sort(key=_clean_counterparty_sort_key)
        return cps

    async def save_counterparty(self, counterparty: Counterparty) -> Counterparty:
        """Save counterparty record.

        Args:
            counterparty: Counterparty domain model.

        Returns:
            Persisted Counterparty instance.
        """
        return await self.repository.save_counterparty(counterparty)

    async def delete_counterparty(self, counterparty_id: int) -> None:
        """Delete counterparty record.

        Args:
            counterparty_id: Target counterparty identifier.
        """
        await self.repository.delete_counterparty(counterparty_id)

    async def get_counterparty_by_keyword(self, keyword: str) -> Counterparty | None:
        """Find counterparty matching substring.

        Args:
            keyword: Substring to search.

        Returns:
            Matched Counterparty model or None.
        """
        if not keyword:
            return None
        return await self.repository.get_counterparty_by_keyword(keyword)
