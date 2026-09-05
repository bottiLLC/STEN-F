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

from datetime import date
import pandas as pd
import streamlit as st
import structlog

from app.config import settings
from app.domain.models.abstract import Abstract
from app.domain.models.account import Account, AccountType
from app.domain.models.corporation import Corporation
from app.domain.models.counterparty import Counterparty
from app.domain.models.fiscal_year import FiscalYear
from app.ui.async_helper import run_async
from app.ui.di import DI
from app.ui.styles import apply_accounting_styles

log = structlog.get_logger()
apply_accounting_styles()

st.header("マスタ・システム管理", divider="blue")
st.caption(
    "事業者情報、会計年度・決算締め処理、勘定科目、取引先、よく使う摘要、バックアップを管理します。"
)

tab_corp, tab_fy, tab_acc, tab_cp, tab_abs, tab_backup = st.tabs(
    [
        "🏢 自社情報",
        "📅 会計年度・年度締め",
        "📑 勘定科目",
        "🤝 取引先",
        "💬 よく使う摘要",
        "💾 バックアップ",
    ]
)

# ==============================================================================
# 1. Corporation Info Tab
# ==============================================================================
with tab_corp:
    st.subheader("自社・事業者情報設定")

    async def fetch_corp():
        async with DI.get_master_service() as service:
            return await service.get_corporation()

    corp = run_async(fetch_corp())

    with st.form("corp_form"):
        corp_name = st.text_input("法人名 / 屋号", value=corp.name if corp else "")
        corp_addr = st.text_input(
            "本店所在地 / 住所",
            value=corp.address if corp and corp.address else "",
        )
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            corp_rep_title = st.text_input(
                "代表役職名 (例: 代表取締役 / 代表社員 / 事業主)",
                value=corp.representative_title
                if corp and corp.representative_title
                else "",
            )
        with col_c2:
            corp_rep_name = st.text_input(
                "代表者氏名",
                value=corp.representative_name
                if corp and corp.representative_name
                else "",
            )

        if st.form_submit_button("💾 保存する", type="primary", icon=":material/save:"):
            if corp_name:
                new_corp = Corporation(
                    name=corp_name,
                    address=corp_addr.strip() if corp_addr.strip() else None,
                    representative_title=corp_rep_title.strip()
                    if corp_rep_title.strip()
                    else None,
                    representative_name=corp_rep_name.strip()
                    if corp_rep_name.strip()
                    else None,
                )

                async def save_corp():
                    async with DI.get_master_service() as service:
                        await service.save_corporation(new_corp)

                try:
                    run_async(save_corp())
                    st.toast("自社情報を保存しました！", icon="✅")
                    st.success("自社情報を正常に更新しました。")
                    st.rerun()
                except Exception as e:
                    st.error(f"保存エラー: {e}")
            else:
                st.error("法人名/屋号を入力してください。")

# ==============================================================================
# 2. Fiscal Year Tab
# ==============================================================================
with tab_fy:
    st.subheader("会計年度の管理・年度締め (Closing)")

    async def fetch_fys():
        async with DI.get_master_service() as service:
            return await service.get_fiscal_years()

    fys = run_async(fetch_fys())

    if fys:
        fy_df = pd.DataFrame(
            [
                {
                    "ID": f.id,
                    "年度名称": f.name,
                    "開始日": f.start_date.isoformat(),
                    "終了日": f.end_date.isoformat(),
                    "期数": f.period_number or "-",
                    "状態": "🟢 進行中 (OPEN)"
                    if f.status == "OPEN"
                    else "🔒 締切済 (CLOSED)",
                }
                for f in fys
            ]
        )
        st.dataframe(fy_df, hide_index=True, use_container_width=True)

    st.markdown("---")
    col_fy1, col_fy2 = st.columns(2)

    with col_fy1:
        st.markdown("### ➕ 新規会計年度の追加")
        with st.form("add_fy_form"):
            new_fy_name = st.text_input("年度名 (例: 2026年度 / 第2期)")
            new_fy_start = st.date_input("開始日", value=date.today())
            new_fy_end = st.date_input("終了日", value=date.today())
            new_fy_period = st.number_input("期数", min_value=1, value=1)

            if st.form_submit_button("会計年度を登録", icon=":material/add:"):
                if new_fy_name:
                    fy_obj = FiscalYear(
                        name=new_fy_name,
                        start_date=new_fy_start,
                        end_date=new_fy_end,
                        period_number=int(new_fy_period),
                        status="OPEN",
                    )

                    async def save_fy():
                        async with DI.get_master_service() as service:
                            await service.save_fiscal_year(fy_obj)

                    run_async(save_fy())
                    st.toast("会計年度を登録しました！", icon="✅")
                    st.rerun()
                else:
                    st.error("年度名を入力してください。")

    with col_fy2:
        st.markdown("### 🔒 年度締め・次期繰越処理")
        open_fys = [f for f in fys if f.status == "OPEN"]
        if open_fys:
            selected_close_fy = st.selectbox(
                "締める会計年度を選択",
                open_fys,
                format_func=lambda x: f"{x.name} ({x.start_date} 〜 {x.end_date})",
            )
            next_fy_name = st.text_input("次期の年度名称 (例: 第3期 / 2027年度)")

            if st.button(
                "この年度を締め切る (CLOSED)", type="secondary", icon=":material/lock:"
            ):
                if next_fy_name:
                    with st.spinner("決算繰越処理を実行中..."):
                        try:

                            async def execute_closing():
                                async with DI.get_fiscal_year_service() as service:
                                    await service.close_fiscal_year(
                                        selected_close_fy.id, next_fy_name
                                    )

                            run_async(execute_closing())
                            st.toast(
                                f"{selected_close_fy.name} を締め切り、{next_fy_name} を開設しました！",
                                icon="🎉",
                            )
                            st.success("年度締めおよび次期繰越処理が完了しました。")
                            st.rerun()
                        except Exception as e:
                            log.error(
                                "Fiscal year closing failed",
                                error=str(e),
                                exc_info=True,
                            )
                            st.error(f"決算処理エラー: {e}")
                else:
                    st.warning("次期の年度名称を入力してください。")
        else:
            st.info("現在 OPEN 状態の会計年度はありません。")

# ==============================================================================
# 3. Account Master Tab
# ==============================================================================
with tab_acc:
    st.subheader("勘定科目マスタ")

    async def fetch_accounts():
        async with DI.get_master_service() as service:
            return await service.get_accounts()

    accs = run_async(fetch_accounts())

    if accs:
        acc_df = pd.DataFrame(
            [
                {
                    "科目コード": a.code,
                    "勘定科目名": a.name,
                    "区分": a.type.label if hasattr(a.type, "label") else str(a.type),
                }
                for a in sorted(accs, key=lambda x: int(x.code))
            ]
        )
        st.dataframe(acc_df, hide_index=True, use_container_width=True)

    with st.expander("＋ 新規勘定科目を追加"):
        with st.form("new_acc_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                n_code = st.text_input("科目コード (例: 6150)")
            with c2:
                n_name = st.text_input("勘定科目名 (例: 研修費)")
            with c3:
                n_type = st.selectbox(
                    "科目区分",
                    [
                        AccountType.CURRENT_ASSET,
                        AccountType.FIXED_ASSET,
                        AccountType.DEFERRED_ASSET,
                        AccountType.CURRENT_LIABILITY,
                        AccountType.FIXED_LIABILITY,
                        AccountType.EQUITY,
                        AccountType.REVENUE,
                        AccountType.COST_OF_SALES,
                        AccountType.SGA,
                        AccountType.NON_OPERATING_INCOME,
                        AccountType.NON_OPERATING_EXPENSE,
                        AccountType.EXTRAORDINARY_INCOME,
                        AccountType.EXTRAORDINARY_LOSS,
                        AccountType.TAXES,
                    ],
                    format_func=lambda x: x.label if hasattr(x, "label") else str(x),
                )

            if st.form_submit_button("科目を追加", icon=":material/add:"):
                if n_code and n_name:
                    new_acc = Account(code=n_code, name=n_name, type=n_type)

                    async def save_acc():
                        async with DI.get_master_service() as service:
                            await service.save_account(new_acc)

                    try:
                        run_async(save_acc())
                        st.toast("勘定科目を追加しました！", icon="✅")
                        st.rerun()
                    except Exception as e:
                        st.error(f"追加エラー: {e}")
                else:
                    st.error("コードと科目名を入力してください。")

# ==============================================================================
# 4. Counterparty Master Tab
# ==============================================================================
with tab_cp:
    st.subheader("取引先マスタ")

    async def fetch_cps():
        async with DI.get_master_service() as service:
            return await service.get_counterparties()

    cps = run_async(fetch_cps())

    if cps:
        cp_df = pd.DataFrame(
            [
                {
                    "ID": c.id,
                    "取引先名": c.name,
                    "登録番号 (T番号)": c.invoice_number or "-",
                    "推奨借方科目ID": c.debit_account_id or "-",
                    "推奨貸方科目ID": c.credit_account_id or "-",
                }
                for c in cps
            ]
        )
        st.dataframe(cp_df, hide_index=True, use_container_width=True)

    with st.expander("＋ 新規取引先を追加"):
        with st.form("new_cp_form"):
            cp_n = st.text_input("取引先名")
            cp_inv = st.text_input("インボイス登録番号 (T+13桁)")

            if st.form_submit_button("取引先を追加", icon=":material/add:"):
                if cp_n:
                    new_c = Counterparty(
                        name=cp_n,
                        invoice_number=cp_inv.strip().upper()
                        if cp_inv.strip()
                        else None,
                    )

                    async def save_cp():
                        async with DI.get_master_service() as service:
                            await service.save_counterparty(new_c)

                    run_async(save_cp())
                    st.toast("取引先を登録しました！", icon="✅")
                    st.rerun()
                else:
                    st.error("取引先名を入力してください。")

# ==============================================================================
# 5. Abstract Suggestions Tab
# ==============================================================================
with tab_abs:
    st.subheader("よく使う摘要マスタ")

    async def fetch_abs():
        async with DI.get_master_service() as service:
            return await service.get_abstracts()

    abstracts = run_async(fetch_abs())

    if abstracts:
        abs_df = pd.DataFrame(
            [
                {
                    "ID": ab.id,
                    "摘要テキスト": ab.text,
                    "関連科目ID": ab.account_id or "全般",
                }
                for ab in abstracts
            ]
        )
        st.dataframe(abs_df, hide_index=True, use_container_width=True)

    with st.expander("＋ 新規摘要を追加"):
        with st.form("new_abs_form"):
            abs_text = st.text_input("摘要テキスト (例: 会議費（飲食代）)")
            acc_choice_map = {f"{a.code}: {a.name}": a.id for a in accs}
            selected_acc_label = st.selectbox(
                "紐づける勘定科目", list(acc_choice_map.keys())
            )

            if st.form_submit_button("摘要を追加", icon=":material/add:"):
                if abs_text and selected_acc_label:
                    target_aid = acc_choice_map[selected_acc_label]
                    new_ab = Abstract(account_id=target_aid, text=abs_text)

                    async def save_ab():
                        async with DI.get_master_service() as service:
                            await service.save_abstract(new_ab)

                    run_async(save_ab())
                    st.toast("摘要を追加しました！", icon="✅")
                    st.rerun()
                else:
                    st.error("摘要テキストと勘定科目を入力してください。")

# ==============================================================================
# 6. Backup Tab
# ==============================================================================
with tab_backup:
    st.subheader("データベース & 設定バックアップ")

    default_backup_dir = str((settings.PROJECT_ROOT / "backups").resolve())
    target_backup_dir = st.text_input(
        "バックアップ先フォルダパス",
        value=default_backup_dir,
        help="バックアップファイル（SQLite DB 及び .env）を退避するディレクトリを指定します。",
    )

    if st.button(
        "💾 ワンクリック・バックアップを実行",
        type="primary",
        icon=":material/backup:",
    ):
        with st.spinner("バックアップを作成中..."):
            try:
                backup_service = DI.get_backup_service()
                saved_path = run_async(backup_service.create_backup(target_backup_dir))
                st.toast("バックアップが完了しました！", icon="🎉")
                st.success(
                    f"バックアップが正常に作成されました。\n\n**保存先:** `{saved_path}`"
                )
            except Exception as e:
                log.error("Backup failed", error=str(e), exc_info=True)
                st.error(f"バックアップ作成エラー: {e}")

    st.info(
        "💡 **証憑 PDF / 画像のバックアップについて**\n\n"
        "電子帳簿保存法に対応して蓄積された領収書・請求書ファイルは `storage/` フォルダに保管されています。"
        "データ容量が大きくなるため、上記の DB バックアップと併せて `storage/` フォルダごと外部ストレージやクラウドへ定期的にコピー・同期保存してください。"
    )
