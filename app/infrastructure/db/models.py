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

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import Column, Integer, String, Date, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import DeclarativeBase, relationship
from app.config import settings

DATABASE_URL = settings.DATABASE_URL
assert DATABASE_URL is not None

engine = create_async_engine(DATABASE_URL, echo=False)

class Base(DeclarativeBase):
    pass

class AccountTable(Base):
    __tablename__ = 'accounts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    description = Column(String, nullable=True)

class CorporationTable(Base):
    __tablename__ = 'corporation'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)

    address = Column(String, nullable=True)
    representative_title = Column(String, nullable=True)
    representative_name = Column(String, nullable=True)

class CounterpartyTable(Base):
    __tablename__ = 'counterparties'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    name_kana = Column(String, nullable=True)
    invoice_number = Column(String, unique=True, nullable=True)
    debit_account_id = Column(Integer, ForeignKey('accounts.id'), nullable=True)
    credit_account_id = Column(Integer, ForeignKey('accounts.id'), nullable=True)
    description_template = Column(String, nullable=True)

class FiscalYearTable(Base):
    __tablename__ = 'fiscal_years'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String, default='OPEN')
    period_number = Column(Integer, nullable=True)
    # created_at is strictly handled by DB defaults usually, but we map it if needed. 
    # For now, simplistic map.

class AbstractTable(Base):
    __tablename__ = 'abstracts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    text = Column(String, nullable=False)
    
    account = relationship("AccountTable")

class TransactionTable(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    description = Column(String, nullable=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    counterparty = Column(String, nullable=True)
    invoice_number = Column(String, nullable=True)
    evidence_path = Column(String, nullable=True)
    
    lines = relationship("TransactionLineTable", back_populates="transaction", cascade="all, delete-orphan")

class TransactionLineTable(Base):
    __tablename__ = 'transaction_lines'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(Integer, ForeignKey('transactions.id'), nullable=False)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    debit = Column(Integer, default=0)
    credit = Column(Integer, default=0)
    
    transaction = relationship("TransactionTable", back_populates="lines")
    account = relationship("AccountTable")

class SystemTable(Base):
    __tablename__ = 'system_config'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ai_api_key = Column(String, nullable=True)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
