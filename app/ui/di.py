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
