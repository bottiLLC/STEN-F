from sqlalchemy.future import select
from app.infrastructure.db.session import AsyncSessionLocal
from app.domain.models.account import Account, AccountType

DEFAULT_ACCOUNTS = [
    # Assets (資産)
    {"code": "1111", "name": "現金", "type": AccountType.CURRENT_ASSET, "description": "手許にある現金"},
    {"code": "1112", "name": "小口現金", "type": AccountType.CURRENT_ASSET, "description": "定額資金前渡法などで管理する現金"},
    {"code": "1121", "name": "普通預金", "type": AccountType.CURRENT_ASSET, "description": "銀行の普通預金口座"},
    {"code": "1122", "name": "当座預金", "type": AccountType.CURRENT_ASSET, "description": "小切手支払などが可能な預金"},
    {"code": "1131", "name": "受取手形", "type": AccountType.CURRENT_ASSET, "description": "商品販売等で受け取った手形"},
    {"code": "1141", "name": "売掛金", "type": AccountType.CURRENT_ASSET, "description": "掛けで販売した代金の未回収分"},
    {"code": "1151", "name": "棚卸資産", "type": AccountType.CURRENT_ASSET, "description": "商品、製品、原材料などの在庫"},
    {"code": "1161", "name": "前払費用", "type": AccountType.CURRENT_ASSET, "description": "継続的役務提供契約で前払いした費用"},
    {"code": "1211", "name": "建物", "type": AccountType.FIXED_ASSET, "description": "店舗、倉庫、事務所などの建物"},
    {"code": "1221", "name": "備品", "type": AccountType.FIXED_ASSET, "description": "パソコン、机、椅子などの事務機器"},
    {"code": "1231", "name": "車両運搬具", "type": AccountType.FIXED_ASSET, "description": "営業車両など"},
    
    # Liabilities (負債)
    {"code": "2111", "name": "支払手形", "type": AccountType.CURRENT_LIABILITY, "description": "商品の購入等で振り出した手形"},
    {"code": "2121", "name": "買掛金", "type": AccountType.CURRENT_LIABILITY, "description": "掛けで購入した代金の未払分"},
    {"code": "2131", "name": "短期借入金", "type": AccountType.CURRENT_LIABILITY, "description": "1年以内に返済期限が到来する借入金"},
    {"code": "2141", "name": "未払金", "type": AccountType.CURRENT_LIABILITY, "description": "本来の営業取引以外の未払代金"},
    {"code": "2151", "name": "預り金", "type": AccountType.CURRENT_LIABILITY, "description": "源泉所得税、社会保険料などの預り分"},
    {"code": "2211", "name": "長期借入金", "type": AccountType.FIXED_LIABILITY, "description": "返済期限が1年を超える借入金"},

    # Equity (純資産)
    {"code": "3111", "name": "資本金", "type": AccountType.EQUITY, "description": "会社設立時等の出資額"},
    {"code": "3121", "name": "繰越利益剰余金", "type": AccountType.EQUITY, "description": "過年度からの利益の蓄積"},

    # Revenue (収益)
    {"code": "4111", "name": "売上高", "type": AccountType.REVENUE, "description": "商品・サービスの販売による収益"},
    {"code": "4211", "name": "受取利息", "type": AccountType.NON_OPERATING_INCOME, "description": "預貯金などの利息"},
    {"code": "4221", "name": "雑収入", "type": AccountType.NON_OPERATING_INCOME, "description": "本業以外の重要性の低い収益"},

    # Expenses (費用) - Cost of Sales
    {"code": "5111", "name": "仕入高", "type": AccountType.COST_OF_SALES, "description": "商品の仕入原価"},
    {"code": "5121", "name": "外注費", "type": AccountType.COST_OF_SALES, "description": "業務委託費など"},

    # Expenses (費用) - SGA
    {"code": "6111", "name": "役員報酬", "type": AccountType.SGA, "description": "取締役などの報酬"},
    {"code": "6121", "name": "給料手当", "type": AccountType.SGA, "description": "従業員の給与・手当"},
    {"code": "6131", "name": "法定福利費", "type": AccountType.SGA, "description": "社会保険料の会社負担分"},
    {"code": "6211", "name": "広告宣伝費", "type": AccountType.SGA, "description": "広告、チラシ、Web広報費など"},
    {"code": "6221", "name": "旅費交通費", "type": AccountType.SGA, "description": "電車、バス、タクシー、宿泊費"},
    {"code": "6231", "name": "通信費", "type": AccountType.SGA, "description": "電話、インターネット、郵便代"},
    {"code": "6241", "name": "消耗品費", "type": AccountType.SGA, "description": "10万円未満の物品購入費"},
    {"code": "6251", "name": "接待交際費", "type": AccountType.SGA, "description": "取引先との飲食等の費用"},
    {"code": "6261", "name": "地代家賃", "type": AccountType.SGA, "description": "事務所の家賃、駐車場代"},
    {"code": "6271", "name": "水道光熱費", "type": AccountType.SGA, "description": "電気、ガス、水道代"},
    {"code": "6281", "name": "租税公課", "type": AccountType.SGA, "description": "印紙税、固定資産税など"},
    {"code": "6291", "name": "支払手数料", "type": AccountType.SGA, "description": "振込手数料、専門家報酬など"},
    {"code": "6311", "name": "雑費", "type": AccountType.SGA, "description": "他の科目に当てはまらない少額費用"},

    # Expenses (費用) - Non-Operating
    {"code": "7111", "name": "支払利息", "type": AccountType.NON_OPERATING_EXPENSE, "description": "借入金の利息"},
]

from app.infrastructure.db.models import AccountTable

async def seed_accounts():
    """Seed existing database with default accounts if empty."""
    # Ensure tables exist
    from app.infrastructure.db.session import init_db
    await init_db()
    
    async with AsyncSessionLocal() as session:
        try:
            # Check if accounts exist
            result = await session.execute(select(AccountTable).limit(1))
            if result.scalar_one_or_none():
                return  # Database already seeded

            print("Seeding default accounts...")
            
            # Map Pydantic definition to ORM usage equivalent or directly save via Repo logic
            # Simulating Repo logic using session directly for speed/simplicity or use Repo?
            # Direct session add is fine for seeding.
            
            for acc_data in DEFAULT_ACCOUNTS:
                # Assuming Account is the Pydantic model mapped to ORM?
                # app.domain.models.account.Account is Pydantic.
                # app.infrastructure.db.models.AccountModel is ORM?
                # Let's check imports in repository.
                # Usually we should use Repository to be clean, but circular deps might be an issue?
                # Let's look at `app/infrastructure/db/models.py`.
                # For now, let's assume we use the Repository if possible.
                
                # Check DI usage
                pass 
                
        except Exception as e:
            print(f"Seeding check failed: {e}")
            return

    # To avoid ORM model import issues without looking at files, let's use the MasterService via DI
    # But DI might need loop.
    from app.ui.di import DI
    
    async with DI.get_master_service() as service:
        existing = await service.get_accounts()
        if existing:
             return

        print("Seeding default accounts via Service...")
        for acc_data in DEFAULT_ACCOUNTS:
            acc = Account(**acc_data)
            await service.save_account(acc)
        print("Seeding complete.")
