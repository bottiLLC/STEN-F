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

from app.container import container


class DI:
    @staticmethod
    def get_journal_service():
        return container.journal_service_scope()

    @staticmethod
    def get_master_service():
        return container.master_service_scope()

    @staticmethod
    def get_ledger_service():
        return container.ledger_service_scope()

    @staticmethod
    def get_fiscal_year_service():
        return container.fiscal_year_service_scope()

    @staticmethod
    def get_ocr_service():
        return container.get_ocr_service()

    @staticmethod
    def get_file_service():
        return container.get_file_service()

    @staticmethod
    def get_backup_service():
        return container.get_backup_service()

    @staticmethod
    def get_pdf_service():
        return container.get_pdf_service()
