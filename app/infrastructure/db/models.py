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

import datetime
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from app.config import settings

DATABASE_URL = settings.DATABASE_URL
assert DATABASE_URL is not None

engine = create_async_engine(DATABASE_URL, echo=False)


class Base(DeclarativeBase):
    pass


class AccountTable(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    type: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(nullable=True)


class CorporationTable(Base):
    __tablename__ = "corporation"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    address: Mapped[str | None] = mapped_column(nullable=True)
    representative_title: Mapped[str | None] = mapped_column(nullable=True)
    representative_name: Mapped[str | None] = mapped_column(nullable=True)


class CounterpartyTable(Base):
    __tablename__ = "counterparties"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    name_kana: Mapped[str | None] = mapped_column(nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(unique=True, nullable=True)
    debit_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    credit_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    description_template: Mapped[str | None] = mapped_column(nullable=True)


class FiscalYearTable(Base):
    __tablename__ = "fiscal_years"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    start_date: Mapped[datetime.date] = mapped_column(nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(default="OPEN")
    period_number: Mapped[int | None] = mapped_column(nullable=True)


class AbstractTable(Base):
    __tablename__ = "abstracts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    text: Mapped[str] = mapped_column(nullable=False)

    account: Mapped["AccountTable"] = relationship("AccountTable")


class TransactionTable(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[datetime.date] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(nullable=True)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    counterparty: Mapped[str | None] = mapped_column(nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(nullable=True)
    evidence_path: Mapped[str | None] = mapped_column(nullable=True)

    lines: Mapped[list["TransactionLineTable"]] = relationship(
        "TransactionLineTable",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )


class TransactionLineTable(Base):
    __tablename__ = "transaction_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id"), nullable=False
    )
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    debit: Mapped[int] = mapped_column(default=0)
    credit: Mapped[int] = mapped_column(default=0)

    transaction: Mapped["TransactionTable"] = relationship(
        "TransactionTable", back_populates="lines"
    )
    account: Mapped["AccountTable"] = relationship("AccountTable")


class SystemTable(Base):
    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ai_api_key: Mapped[str | None] = mapped_column(nullable=True)
    backup_path: Mapped[str | None] = mapped_column(nullable=True)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
