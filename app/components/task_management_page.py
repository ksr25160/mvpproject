"""
Meeting AI Assistant - Task Management 페이지 렌더링
"""
import streamlit as st

def render_task_management(service_manager):
    """작업 관리 페이지 렌더링"""
    with st.container():
        st.markdown("# ✅ Task Management")
        st.markdown("---")
        
        # 작업 목록 조회
        try:
            # 모든 액션 아이템을 한 번에 조회 (성능 개선)
            all_action_items = service_manager.get_all_action_items()
            
            # 회의 제목을 액션 아이템에 추가
            meetings = service_manager.get_meetings()
            meeting_titles = {meeting.get('id'): meeting.get('title', 'Unknown') for meeting in meetings}
            
            for item in all_action_items:
                meeting_id = item.get('meetingId')
                item['meeting_title'] = meeting_titles.get(meeting_id, 'Unknown')
            
            if not all_action_items:
                st.info("📋 등록된 작업이 없습니다. 회의를 분석하여 자동으로 작업을 생성해보세요!")
            else:
                # 작업 현황 요약
                total_tasks = len(all_action_items)
                completed_tasks = len([item for item in all_action_items if item.get('status') == '완료'])
                pending_tasks = total_tasks - completed_tasks
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("전체 작업", total_tasks)
                with col2:
                    st.metric("완료", completed_tasks, f"{(completed_tasks/total_tasks*100):.1f}%" if total_tasks > 0 else "0%")
                with col3:
                    st.metric("대기중", pending_tasks)
                    st.markdown("---")
                
                # 작업 필터
                tab1, tab2, tab3 = st.tabs(["📋 전체", "⏳ 대기중", "✅ 완료"])
                
                with tab1:
                    render_task_list(all_action_items, "all", service_manager)
                
                with tab2:
                    pending_items = [item for item in all_action_items if item.get('status') != '완료']
                    render_task_list(pending_items, "pending", service_manager)
                
                with tab3:
                    completed_items = [item for item in all_action_items if item.get('status') == '완료']
                    render_task_list(completed_items, "completed", service_manager)
        
        except Exception as e:
            st.error(f"❌ 작업 목록을 불러오는 중 오류가 발생했습니다: {str(e)}")

def render_task_list(tasks, task_type, service_manager):
    """작업 목록 렌더링"""
    if not tasks:
        if task_type == "pending":
            st.info("🎉 모든 작업이 완료되었습니다!")
        elif task_type == "completed":
            st.info("📋 완료된 작업이 없습니다.")
        else:
            st.info("📋 등록된 작업이 없습니다.")
        return
    
    for i, task in enumerate(tasks):
        with st.container():
            col1, col2, col3 = st.columns([6, 2, 2])
            
            with col1:
                status_icon = "✅" if task.get('status') == '완료' else "⏳"
                description = task.get('description', task.get('task', 'N/A'))
                st.write(f"{status_icon} **{description}**")
                
                meeting_title = task.get('meeting_title', 'N/A')
                assignee = task.get('finalAssigneeId', task.get('recommendedAssigneeId', task.get('assignee', 'N/A')))
                due_date = task.get('dueDate', task.get('due_date', 'N/A'))
                
                st.caption(f"회의: {meeting_title} | 담당자: {assignee} | 기한: {due_date}")
            
            with col2:
                priority = task.get('priority', 'Medium')
                if priority == 'High':
                    st.error(f"🔴 {priority}")
                elif priority == 'Medium':
                    st.warning(f"🟡 {priority}")
                else:
                    st.info(f"🟢 {priority}")
                    
            with col3:
                if task.get('status') != '완료':
                    task_id = task.get('id', f"task_{i}")
                    meeting_id = task.get('meetingId', '')
                    
                    # 고유한 키 생성 (task_type과 인덱스 포함)
                    unique_key = f"complete_{task_type}_{task_id}_{i}"
                    if st.button("완료", key=unique_key):
                        try:
                            if meeting_id:
                                service_manager.update_action_item_status(task_id, meeting_id, '완료')
                                st.success("✅ 작업이 완료로 표시되었습니다!")
                                st.rerun()
                            else:
                                st.error("❌ 회의 ID가 없어 상태를 업데이트할 수 없습니다.")
                        except Exception as e:
                            st.error(f"❌ 오류: {str(e)}")
            
            st.markdown("---")
