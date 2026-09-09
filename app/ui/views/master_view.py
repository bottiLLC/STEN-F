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

from app.domain.models.abstract import Abstract
from app.domain.models.account import Account, AccountType
from app.domain.models.corporation import Corporation
from app.domain.models.counterparty import Counterparty
from app.domain.models.fiscal_year import FiscalYear
from app.domain.models.system import SystemSettings
from app.ui.async_helper import run_async
from app.ui.di import DI
from app.ui.editor import render_accounting_editor

log = structlog.get_logger()

st.header("マスタ・システム設定ワークスペース", divider="blue")
st.caption(
    "事業者情報、会計年度・決算締め処理、期首残高、勘定科目・取引先・摘要マスタ、バックアップ、AI設定を一括管理します。"
)

tab_corp, tab_fy, tab_op, tab_acc, tab_cp, tab_abs, tab_backup, tab_sys = st.tabs(
    [
        "🏢 自社情報",
        "📅 会計年度・年度締め",
        "⚖️ 期首残高設定",
        "📑 勘定科目",
        "🤝 取引先",
        "💬 よく使う摘要",
        "💾 バックアップ",
        "⚙️ AI・システム設定",
    ]
)

# 1. 自社情報
with tab_corp:
    st.subheader("自社・事業者情報設定")

    async def fetch_corp():
        async with DI.get_master_service() as s:
            return await s.get_corporation()

    corp = run_async(fetch_corp())
    with st.form("corp_form"):
        corp_name = st.text_input("法人名 / 屋号", value=corp.name if corp else "")
        corp_addr = st.text_input(
            "本店所在地 / 住所", value=corp.address if corp and corp.address else ""
        )
        c1, c2 = st.columns(2)
        corp_rep_title = c1.text_input(
            "代表者役職",
            value=corp.representative_title
            if corp and corp.representative_title
            else "代表社員",
        )
        corp_rep_name = c2.text_input(
            "代表者氏名",
            value=corp.representative_name if corp and corp.representative_name else "",
        )

        if st.form_submit_button(
            "💾 自社情報を保存する", type="primary", use_container_width=True
        ):
            if not corp_name.strip():
                st.error("法人名・屋号を入力してください。")
            else:
                updated_corp = Corporation(
                    id=corp.id if corp else None,
                    name=corp_name.strip(),
                    address=corp_addr.strip() if corp_addr else None,
                    representative_title=corp_rep_title.strip()
                    if corp_rep_title
                    else None,
                    representative_name=corp_rep_name.strip()
                    if corp_rep_name
                    else None,
                )

                async def save_corp(c):
                    async with DI.get_master_service() as s:
                        return await s.save_corporation(c)

                run_async(save_corp(updated_corp))
                st.success("自社情報を保存しました！")
                st.rerun()

# 2. 会計年度・年度締め
with tab_fy:
    st.subheader("会計年度一覧 ＆ 年度締め処理")

    async def fetch_fys():
        async with DI.get_master_service() as s:
            return await s.get_fiscal_years()

    fys = run_async(fetch_fys())
    col_fy_list, col_fy_new = st.columns([3, 2])
    with col_fy_list:
        if fys:
            fy_rows = [
                {
                    "ID": f.id,
                    "年度名称": f.name,
                    "期数": f"第{f.period_number}期" if f.period_number else "-",
                    "開始日": str(f.start_date),
                    "終了日": str(f.end_date),
                    "状態": "進行中 (OPEN)"
                    if f.status == "OPEN"
                    else "締切済 (CLOSED)",
                }
                for f in sorted(fys, key=lambda x: x.start_date, reverse=True)
            ]
            st.dataframe(
                pd.DataFrame(fy_rows), hide_index=True, use_container_width=True
            )
        else:
            st.info("登録済みの会計年度がありません。")

        open_fy = next((f for f in fys if f.status == "OPEN"), None)
        if open_fy:
            st.markdown("---")
            st.markdown(f"#### 🔒 会計年度の締め処理 (現在進行中: `{open_fy.name}`)")
            with st.form("fy_close_form"):
                next_fy_name = st.text_input(
                    "次期年度名称", value=f"第{(open_fy.period_number or 0) + 1}期"
                )
                if st.form_submit_button(
                    "⚠️ この会計年度を締め切る (CLOSED)",
                    type="primary",
                    use_container_width=True,
                ):

                    async def do_close(fid, nname):
                        async with DI.get_fiscal_year_service() as s:
                            await s.close_fiscal_year(fid, nname)

                    try:
                        run_async(do_close(open_fy.id, next_fy_name))
                        st.success("年度締め処理が完了し、次期が作成されました！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"年度締めエラー: {e}")

    with col_fy_new:
        st.markdown("#### ➕ 新規会計年度の登録")
        with st.form("new_fy_form"):
            new_name = st.text_input("年度名称 (例: 第1期)")
            new_period = st.number_input("期数", min_value=1, value=1)
            c_d1, c_d2 = st.columns(2)
            new_start = c_d1.date_input("開始日", value=date(date.today().year, 1, 1))
            new_end = c_d2.date_input("終了日", value=date(date.today().year, 12, 31))

            if st.form_submit_button(
                "登録する", type="primary", use_container_width=True
            ):
                if new_start >= new_end:
                    st.error("終了日は開始日より後の日付を指定してください。")
                elif not new_name.strip():
                    st.error("年度名称を入力してください。")
                else:
                    new_fy = FiscalYear(
                        name=new_name.strip(),
                        period_number=int(new_period),
                        start_date=new_start,
                        end_date=new_end,
                        status="OPEN",
                    )

                    async def save_new_fy(f):
                        async with DI.get_master_service() as s:
                            return await s.save_fiscal_year(f)

                    run_async(save_new_fy(new_fy))
                    st.success("会計年度を登録しました！")
                    st.rerun()

# 3. 期首残高設定
with tab_op:
    st.subheader("期首残高設定 (開始貸借対照表)")

    async def fetch_op_data():
        async with DI.get_master_service() as s:
            f = await s.get_fiscal_years()
            return next(
                (x for x in f if x.status == "OPEN"), None
            ), await s.get_accounts()

    open_fy, all_accounts = run_async(fetch_op_data())
    if not open_fy:
        st.warning("進行中 (OPEN) の会計年度がありません。")
    else:
        debit_accs = [
            a
            for a in all_accounts
            if a.type
            in (
                AccountType.CURRENT_ASSET,
                AccountType.FIXED_ASSET,
                AccountType.DEFERRED_ASSET,
            )
        ]
        credit_accs = [
            a
            for a in all_accounts
            if a.type
            in (
                AccountType.CURRENT_LIABILITY,
                AccountType.FIXED_LIABILITY,
                AccountType.EQUITY,
            )
        ]

        with st.form("opening_balance_form"):
            c_l, c_r = st.columns(2)
            op_d, op_c = {}, {}
            with c_l:
                st.markdown("### 【 借方 : 資産の部 】")
                for a in debit_accs:
                    v = st.number_input(
                        f"{a.code}: {a.name}",
                        min_value=0,
                        value=0,
                        step=10000,
                        key=f"op_acc_{a.id}",
                    )
                    if a.id:
                        op_d[str(a.id)] = str(v)
            with c_r:
                st.markdown("### 【 貸方 : 負債・純資産の部 】")
                for a in credit_accs:
                    v = st.number_input(
                        f"{a.code}: {a.name}",
                        min_value=0,
                        value=0,
                        step=10000,
                        key=f"op_acc_{a.id}",
                    )
                    if a.id:
                        op_c[str(a.id)] = str(v)

            total_d, total_c = (
                sum(int(v) for v in op_d.values()),
                sum(int(v) for v in op_c.values()),
            )
            st.markdown("---")
            m1, m2, m3 = st.columns(3)
            m1.metric("資産合計 (借方)", f"¥{total_d:,}")
            m2.metric("負債・純資産合計 (貸方)", f"¥{total_c:,}")
            diff = total_d - total_c
            m3.metric(
                "貸借バランス",
                "✅ 一致" if diff == 0 and total_d > 0 else f"差額: ¥{diff:,}",
            )

            if st.form_submit_button(
                "💾 期首残高を登録・更新する", type="primary", use_container_width=True
            ):
                if diff != 0 or total_d == 0:
                    st.error("貸借合計を一致させ、0より大きい金額を入力してください。")
                else:

                    async def save_op(odate, db, cb):
                        async with DI.get_journal_service() as s:
                            await s.register_opening_balance(odate, db, cb)

                    run_async(save_op(open_fy.start_date, op_d, op_c))
                    st.success("期首残高を登録しました！")
                    st.rerun()

# 4. 勘定科目マスタ
with tab_acc:
    st.subheader("勘定科目マスタ一括管理")

    async def fetch_accounts():
        async with DI.get_master_service() as s:
            return await s.get_accounts()

    acc_list = run_async(fetch_accounts())
    acc_df = pd.DataFrame(
        [
            {
                "id": a.id,
                "code": a.code,
                "name": a.name,
                "type": a.type.value if hasattr(a.type, "value") else str(a.type),
                "description": a.description or "",
            }
            for a in sorted(acc_list, key=lambda x: int(x.code))
        ]
    )

    def on_commit_accounts(added, edited, deleted):
        async def do_commit():
            async with DI.get_master_service() as s:
                for r in added:
                    if r.get("code") and r.get("name") and r.get("type"):
                        await s.save_account(
                            Account(
                                code=str(r["code"]),
                                name=str(r["name"]),
                                type=AccountType(r["type"]),
                                description=r.get("description"),
                            )
                        )
                for pk, chg in edited.items():
                    cur = next((a for a in acc_list if a.id == pk), None)
                    if cur:
                        await s.save_account(
                            Account(
                                id=pk,
                                code=str(chg.get("code", cur.code)),
                                name=str(chg.get("name", cur.name)),
                                type=AccountType(chg.get("type", cur.type)),
                                description=chg.get("description", cur.description),
                            )
                        )
                for pk in deleted:
                    await s.delete_account(pk)

        run_async(do_commit())

    col_cfg_acc = {
        "id": st.column_config.NumberColumn("ID", disabled=True),
        "code": st.column_config.TextColumn("科目コード", required=True),
        "name": st.column_config.TextColumn("科目名", required=True),
        "type": st.column_config.SelectboxColumn(
            "勘定区分", options=[t.value for t in AccountType], required=True
        ),
        "description": st.column_config.TextColumn("説明・用途"),
    }
    render_accounting_editor(
        acc_df,
        pk_column="id",
        base_key="editor_accounts",
        on_commit=on_commit_accounts,
        column_config=col_cfg_acc,
    )

# 5. 取引先マスタ
with tab_cp:
    st.subheader("取引先マスタ一括管理")

    async def fetch_cps():
        async with DI.get_master_service() as s:
            return await s.get_counterparties()

    cps = run_async(fetch_cps())
    cp_df = pd.DataFrame(
        [
            {
                "id": c.id,
                "name": c.name,
                "invoice_number": c.invoice_number or "",
                "debit_account_id": c.debit_account_id or None,
                "credit_account_id": c.credit_account_id or None,
            }
            for c in cps
        ]
    )

    def on_commit_cps(added, edited, deleted):
        async def do_commit():
            async with DI.get_master_service() as s:
                for r in added:
                    if r.get("name"):
                        await s.save_counterparty(
                            Counterparty(
                                name=str(r["name"]),
                                invoice_number=r.get("invoice_number") or None,
                                debit_account_id=int(r["debit_account_id"])
                                if r.get("debit_account_id")
                                else None,
                                credit_account_id=int(r["credit_account_id"])
                                if r.get("credit_account_id")
                                else None,
                            )
                        )
                for pk, chg in edited.items():
                    cur = next((c for c in cps if c.id == pk), None)
                    if cur:
                        await s.save_counterparty(
                            Counterparty(
                                id=pk,
                                name=str(chg.get("name", cur.name)),
                                invoice_number=chg.get(
                                    "invoice_number", cur.invoice_number
                                ),
                                debit_account_id=int(chg["debit_account_id"])
                                if chg.get("debit_account_id")
                                else cur.debit_account_id,
                                credit_account_id=int(chg["credit_account_id"])
                                if chg.get("credit_account_id")
                                else cur.credit_account_id,
                            )
                        )
                for pk in deleted:
                    await s.delete_counterparty(pk)

        run_async(do_commit())

    render_accounting_editor(
        cp_df, pk_column="id", base_key="editor_counterparties", on_commit=on_commit_cps
    )

# 6. よく使う摘要マスタ
with tab_abs:
    st.subheader("よく使う摘要マスタ一括管理")

    async def fetch_abs():
        async with DI.get_master_service() as s:
            return await s.get_abstracts()

    abs_list = run_async(fetch_abs())
    abs_df = pd.DataFrame(
        [{"id": a.id, "text": a.text, "account_id": a.account_id} for a in abs_list]
    )

    def on_commit_abs(added, edited, deleted):
        async def do_commit():
            async with DI.get_master_service() as s:
                for r in added:
                    if r.get("text") and r.get("account_id"):
                        await s.save_abstract(
                            Abstract(
                                text=str(r["text"]), account_id=int(r["account_id"])
                            )
                        )
                for pk, chg in edited.items():
                    cur = next((a for a in abs_list if a.id == pk), None)
                    if cur:
                        await s.save_abstract(
                            Abstract(
                                id=pk,
                                text=str(chg.get("text", cur.text)),
                                account_id=int(chg.get("account_id", cur.account_id)),
                            )
                        )
                for pk in deleted:
                    await s.delete_abstract(pk)

        run_async(do_commit())

    render_accounting_editor(
        abs_df, pk_column="id", base_key="editor_abstracts", on_commit=on_commit_abs
    )

# 7. バックアップ
with tab_backup:
    st.subheader("データベース・設定バックアップ")
    st.caption("SQLite データベースと環境設定ファイルを安全に退避します。")
    backup_dir = st.text_input("バックアップ保存先フォルダ", value="./backups")
    if st.button(
        "💾 ワンクリック・バックアップを実行", type="primary", use_container_width=True
    ):

        async def do_backup(p):
            async with DI.get_backup_service() as s:
                return await s.create_backup(p)

        try:
            bk_path = run_async(do_backup(backup_dir))
            st.success(f"バックアップが正常に完了しました！\n保存先: `{bk_path}`")
        except Exception as e:
            st.error(f"バックアップ失敗: {e}")

# 8. AI・システム設定
with tab_sys:
    st.subheader("⚙️ AI（Google Gemini）＆ システム設定")

    async def fetch_sys():
        async with DI.get_master_service() as s:
            return await s.get_system_settings()

    sys_conf = run_async(fetch_sys())
    with st.form("sys_form"):
        api_key_input = st.text_input(
            "Gemini API キー",
            value=sys_conf.ai_api_key or "",
            type="password",
            help="Google AI Studio で発行された API キー",
        )
        if st.form_submit_button(
            "設定を保存する", type="primary", use_container_width=True
        ):

            async def save_sys(k):
                async with DI.get_master_service() as s:
                    await s.save_system_settings(
                        SystemSettings(ai_api_key=k if k else None)
                    )

            run_async(save_sys(api_key_input.strip()))
            st.success("システム設定を保存しました！")
            st.rerun()
