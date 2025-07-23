"""
Meeting AI Assistant - Task Management 페이지 렌더링
"""
import streamlit as st

def render_task_management(service_manager):
    """작업 관리 페이지 렌더링"""
    with st.container():
        st.markdown("# ✅ 업무 관리")
        st.markdown("---")
        
        # 액션 버튼 섹션
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("🔄 새로고침"):
                st.rerun()
        with col2:
            if st.button("📊 통계 보기"):
                st.session_state.show_task_stats = not st.session_state.get('show_task_stats', False)
        
        # 작업 목록 조회
        try:
            # 모든 액션 아이템을 한 번에 조회 (성능 개선)
            all_action_items = service_manager.get_all_action_items()
            
            # 회의 제목을 액션 아이템에 추가
            meetings = service_manager.get_meetings()
            meeting_titles = {meeting.get('id'): meeting.get('title', 'Unknown') for meeting in meetings}
            
            # 직원 정보 추가 (담당자 이름 매핑)
            staff_list = service_manager.get_all_staff()
            # ID 기반 매핑
            staff_by_id = {str(staff.get('user_id', '')): staff.get('name') for staff in staff_list}
            
            for item in all_action_items:
                meeting_id = item.get('meetingId')
                item['meeting_title'] = meeting_titles.get(meeting_id, 'Unknown')
                
                # 담당자 이름 매핑 개선
                assignee_id = item.get('finalAssigneeId') or item.get('recommendedAssigneeId', '')
                if assignee_id and assignee_id != 'None':
                    # 숫자 ID인 경우 직원 이름으로 변환
                    if str(assignee_id).isdigit():
                        item['assignee_name'] = staff_by_id.get(str(assignee_id), f"직원 {assignee_id}")
                    else:
                        item['assignee_name'] = assignee_id
                else:
                    item['assignee_name'] = '미할당'
            
            if not all_action_items:
                st.info("📋 등록된 작업이 없습니다. 회의를 분석하여 자동으로 작업을 생성해보세요!")
            else:
                # 작업 현황 요약
                total_tasks = len(all_action_items)
                completed_tasks = len([item for item in all_action_items if item.get('status') == '완료'])
                pending_tasks = total_tasks - completed_tasks
                approved_tasks = len([item for item in all_action_items if item.get('approved', False)])
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("전체 작업", total_tasks)
                with col2:
                    st.metric("완료", completed_tasks, f"{(completed_tasks/total_tasks*100):.1f}%" if total_tasks > 0 else "0%")
                with col3:
                    st.metric("대기중", pending_tasks)
                with col4:
                    st.metric("승인됨", approved_tasks)
                
                # 통계 상세 보기
                if st.session_state.get('show_task_stats', False):
                    with st.expander("📊 상세 통계", expanded=True):
                        # 담당자별 작업 현황
                        assignee_stats = {}
                        for item in all_action_items:
                            assignee = item.get('assignee_name', '미할당')
                            if assignee not in assignee_stats:
                                assignee_stats[assignee] = {'total': 0, 'completed': 0}
                            assignee_stats[assignee]['total'] += 1
                            if item.get('status') == '완료':
                                assignee_stats[assignee]['completed'] += 1
                        
                        st.markdown("**👥 담당자별 현황**")
                        for assignee, stats in assignee_stats.items():
                            completion_rate = (stats['completed'] / stats['total'] * 100) if stats['total'] > 0 else 0
                            st.write(f"• {assignee}: {stats['completed']}/{stats['total']} ({completion_rate:.1f}%)")
                
                st.markdown("---")
                
                # 작업 필터
                tab1, tab2, tab3, tab4 = st.tabs(["📋 전체", "⏳ 대기중", "✅ 완료", "🔍 검색"])
                
                with tab1:
                    render_task_list(all_action_items, "all", service_manager)
                
                with tab2:
                    pending_items = [item for item in all_action_items if item.get('status') != '완료']
                    render_task_list(pending_items, "pending", service_manager)
                
                with tab3:
                    completed_items = [item for item in all_action_items if item.get('status') == '완료']
                    render_task_list(completed_items, "completed", service_manager)
                
                with tab4:
                    # 검색 기능
                    search_term = st.text_input("🔍 작업 검색", placeholder="작업 설명, 담당자, 회의 제목으로 검색...")
                    if search_term:
                        filtered_items = [
                            item for item in all_action_items
                            if search_term.lower() in item.get('description', '').lower() or
                               search_term.lower() in item.get('assignee_name', '').lower() or
                               search_term.lower() in item.get('meeting_title', '').lower()
                        ]
                        st.caption(f"검색 결과: {len(filtered_items)}개")
                        render_task_list(filtered_items, "search", service_manager)
                    else:
                        st.info("검색어를 입력하세요.")
        
        except Exception as e:
            st.error(f"❌ 작업 목록을 불러오는 중 오류가 발생했습니다: {str(e)}")

def render_task_list(tasks, task_type, service_manager):
    """작업 목록 렌더링"""
    if not tasks:
        if task_type == "pending":
            st.info("🎉 모든 작업이 완료되었습니다!")
        elif task_type == "completed":
            st.info("📋 완료된 작업이 없습니다.")
        elif task_type == "search":
            st.info("� 검색 결과가 없습니다.")
        else:
            st.info("�📋 등록된 작업이 없습니다.")
        return
    
    for i, task in enumerate(tasks):
        with st.container():
            # 작업 헤더
            col1, col2 = st.columns([8, 2])
            
            with col1:
                status_icon = "✅" if task.get('status') == '완료' else "⏳"
                description = task.get('description', task.get('task', 'N/A'))
                st.markdown(f"### {status_icon} {description}")
                
                # 작업 세부 정보
                col_info1, col_info2, col_info3 = st.columns(3)
                
                with col_info1:
                    st.markdown("**📋 회의**")
                    meeting_title = task.get('meeting_title', 'N/A')
                    st.write(meeting_title)
                    
                with col_info2:
                    st.markdown("**👤 담당자**")
                    assignee = task.get('assignee_name', '미할당')
                    if assignee == '미할당':
                        st.warning(assignee)
                    else:
                        st.write(assignee)
                        
                with col_info3:
                    st.markdown("**📅 마감일**")
                    due_date = task.get('dueDate', task.get('due_date', 'N/A'))
                    st.write(due_date)
                
                # 추가 정보
                approved = task.get('approved', False)
                status = task.get('status', '미시작')
                
                col_extra1, col_extra2 = st.columns(2)
                with col_extra1:
                    if approved:
                        st.success("✅ 승인됨")
                    else:
                        st.warning("⏳ 승인 대기")
                        
                with col_extra2:
                    if status == '완료':
                        st.success("✅ 완료")
                    elif status == '진행중':
                        st.info("🔄 진행중")
                    else:
                        st.warning("📋 미시작")
            
            with col2:
                # 액션 버튼들
                task_id = task.get('id', f"task_{i}")
                meeting_id = task.get('meetingId', '')
                
                # 고유한 키 생성
                unique_key_base = f"{task_type}_{task_id}_{i}"
                
                # 상태 변경 버튼
                if task.get('status') != '완료':
                    status_options = ['미시작', '진행중', '완료']
                    current_status = task.get('status', '미시작')
                    
                    new_status = st.selectbox(
                        "상태 변경:",
                        status_options,
                        index=status_options.index(current_status) if current_status in status_options else 0,
                        key=f"status_{unique_key_base}"
                    )
                    
                    if new_status != current_status:
                        if st.button("상태 변경", key=f"update_status_{unique_key_base}"):
                            try:
                                if meeting_id:
                                    service_manager.update_action_item_status(task_id, meeting_id, new_status)
                                    st.success(f"✅ 상태가 '{new_status}'로 변경되었습니다!")
                                    st.rerun()
                                else:
                                    st.error("❌ 회의 ID가 없어 상태를 업데이트할 수 없습니다.")
                            except Exception as e:
                                st.error(f"❌ 오류: {str(e)}")
                
                # 담당자 변경 버튼
                if st.button("👤 담당자 변경", key=f"assign_{unique_key_base}"):
                    st.session_state[f"show_assign_{unique_key_base}"] = True
                
                # 담당자 변경 폼
                if st.session_state.get(f"show_assign_{unique_key_base}", False):
                    staff_list = service_manager.get_all_staff()
                    staff_options = ['미할당'] + [staff.get('name', 'N/A') for staff in staff_list]
                    
                    current_assignee = task.get('assignee_name', '미할당')
                    
                    new_assignee = st.selectbox(
                        "새 담당자:",
                        staff_options,
                        index=staff_options.index(current_assignee) if current_assignee in staff_options else 0,
                        key=f"assignee_{unique_key_base}"
                    )
                    
                    col_assign1, col_assign2 = st.columns(2)
                    with col_assign1:
                        if st.button("확인", key=f"confirm_assign_{unique_key_base}"):
                            try:
                                if meeting_id:
                                    # 담당자 정보 업데이트
                                    updates = {'finalAssigneeId': new_assignee if new_assignee != '미할당' else None}
                                    service_manager.update_action_item(task_id, meeting_id, updates)
                                    st.success(f"✅ 담당자가 '{new_assignee}'로 변경되었습니다!")
                                    del st.session_state[f"show_assign_{unique_key_base}"]
                                    st.rerun()
                                else:
                                    st.error("❌ 회의 ID가 없어 담당자를 변경할 수 없습니다.")
                            except Exception as e:
                                st.error(f"❌ 오류: {str(e)}")
                    
                    with col_assign2:
                        if st.button("취소", key=f"cancel_assign_{unique_key_base}"):
                            del st.session_state[f"show_assign_{unique_key_base}"]
                            st.rerun()
                
                # 승인 버튼 (승인되지 않은 작업에만 표시)
                if not task.get('approved', False):
                    if st.button("✅ 승인", key=f"approve_{unique_key_base}"):
                        try:
                            if meeting_id:
                                # 승인 처리
                                assignee = task.get('finalAssigneeId') or task.get('recommendedAssigneeId')
                                service_manager.approve_action_item(task_id, meeting_id, assignee, "시스템 관리자")
                                st.success("✅ 작업이 승인되었습니다!")
                                st.rerun()
                            else:
                                st.error("❌ 회의 ID가 없어 승인할 수 없습니다.")
                        except Exception as e:
                            st.error(f"❌ 승인 오류: {str(e)}")
            
            st.markdown("---")
