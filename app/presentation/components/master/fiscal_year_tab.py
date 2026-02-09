import streamlit as st
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from domain.models.fiscal_year import FiscalYear
from presentation.constants import FY_STATUS_JP

if False:
    from application.services.master_service import MasterService

async def render_fiscal_year_tab(master_service: "MasterService"):
    st.subheader("会計年度一覧")
    fys = await master_service.get_fiscal_years()
    
    # List
    if fys:
        for fy in fys:
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            c1.write(f"{fy.name} (第{fy.period_number}期)")
            c2.write(f"{fy.start_date} ~ {fy.end_date}")
            status_disp = FY_STATUS_JP.get(fy.status, fy.status)
            c3.write(f"ステータス: {status_disp}")
            if c4.button("削除", key=f"del_fy_{fy.id}"):
                if await master_service.delete_fiscal_year(fy.id):
                    st.success(f"{fy.name} を削除しました。")
                    st.rerun()
                else:
                    st.error("削除に失敗しました。")
    
    # Search/Add Form
    with st.expander("新規会計年度作成", expanded=not fys):
        with st.form("fy_form"):
            # Smart Defaults Logic
            default_start = date(date.today().year, 4, 1)
            default_period = 1
            
            if fys:
                latest_fy = fys[0] # Repository sorts by start_date desc
                default_start = latest_fy.end_date + timedelta(days=1)
                default_period = latest_fy.period_number + 1
            
            default_end = default_start + relativedelta(years=1) - timedelta(days=1)
            
            fy_name = st.text_input("年度名 (例: 第10期)", value=f"第{default_period}期")
            
            c1, c2 = st.columns(2)
            f_start = c1.date_input("開始日", value=default_start)
            f_end = c2.date_input("終了日", value=default_end)
            
            status = st.selectbox("ステータス", list(FY_STATUS_JP.values()))
            status_key = next((k for k, v in FY_STATUS_JP.items() if v == status), "OPEN")
            
            period_num = st.number_input("期数", min_value=1, step=1, value=default_period)
            
            if st.form_submit_button("追加"):
                new_fy = FiscalYear(
                    name=fy_name,
                    start_date=f_start,
                    end_date=f_end,
                    status=status_key,
                    period_number=int(period_num)
                )
                await master_service.create_fiscal_year(new_fy)
                st.success("会計年度を作成しました。")
                st.rerun()
