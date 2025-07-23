"""
Meeting AI Assistant - Meeting Records 페이지 렌더링
"""
import streamlit as st

def render_meeting_records(service_manager):
    """회의록 페이지 렌더링"""
    with st.container():        
        st.markdown("# 📝 Meeting Records")
        st.markdown("---")
        
        # 회의록 목록 조회
        try:
            meetings = service_manager.get_meetings()
            
            if not meetings:
                st.info("🔍 저장된 회의록이 없습니다. 새로운 회의를 분석해보세요!")
            else:
                # 필터 옵션
                col1, col2 = st.columns([3, 1])
                with col1:
                    search_term = st.text_input("🔍 회의 제목 검색", placeholder="검색어를 입력하세요...")
                with col2:
                    st.write("")  # 여백
                    if st.button("🔄 새로고침", use_container_width=True):
                        st.rerun()
                
                # 회의록 목록 표시
                filtered_meetings = meetings
                if search_term:
                    filtered_meetings = [m for m in meetings if search_term.lower() in m.get('title', '').lower()]
                
                # 안전한 슬라이싱을 위해 리스트 확인
                display_meetings = filtered_meetings[:10] if isinstance(filtered_meetings, list) else []
                
                for meeting in display_meetings:  # 최근 10개만 표시
                    with st.expander(f"📅 {meeting.get('date', 'N/A')} - {meeting.get('title', 'Untitled Meeting')}"):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            # 안전한 참석자 처리
                            participants = meeting.get('participants', [])
                            if isinstance(participants, list):
                                participants_str = ', '.join(participants)
                            else:
                                participants_str = str(participants) if participants else 'N/A'
                            
                            st.write(f"**참석자:** {participants_str}")
                            
                            # 안전한 요약 처리
                            summary = meeting.get('summary', 'N/A')
                            summary_text = summary[:200] + "..." if isinstance(summary, str) and len(summary) > 200 else str(summary)
                            st.write(f"**요약:** {summary_text}")
                            
                            if meeting.get('action_items'):
                                st.write("**액션 아이템:**")
                                action_items = meeting.get('action_items', [])
                                # action_items가 리스트인지 확인
                                if isinstance(action_items, list):
                                    for item in action_items[:3]:
                                        status = "✅" if item.get('completed') else "⏳"
                                        st.write(f"- {status} {item.get('description', 'N/A')}")
                                else:
                                    st.write("- 액션 아이템 형식 오류")
                        
                        with col2:
                            if st.button("📖 상세보기", key=f"detail_{meeting.get('id', '')}"):
                                st.session_state.selected_meeting = meeting
                                st.rerun()
        
        except Exception as e:
            st.error(f"❌ 회의록을 불러오는 중 오류가 발생했습니다: {str(e)}")
