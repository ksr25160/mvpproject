"""
Meeting AI Assistant - Meeting Records 페이지 렌더링
"""

import streamlit as st


def render_meeting_records(service_manager):
    """회의록 페이지 렌더링"""
    with st.container():
        st.markdown("# 📝 회의 기록")
        st.markdown("---")

        # 상세보기 모드 확인
        if st.session_state.get("selected_meeting"):
            render_meeting_detail(service_manager)
            return

        # 회의록 목록 조회
        try:
            meetings = service_manager.get_meetings()

            if not meetings:
                st.info("🔍 저장된 회의록이 없습니다. 새로운 회의를 분석해보세요!")
            else:
                # 필터 옵션
                col1, col2 = st.columns([3, 1])
                with col1:
                    search_term = st.text_input(
                        "🔍 회의 제목 검색", placeholder="검색어를 입력하세요..."
                    )
                with col2:
                    st.write("")  # 여백
                    if st.button("🔄 새로고침", use_container_width=True):
                        st.rerun()

                # 회의록 목록 표시
                filtered_meetings = meetings
                if search_term:
                    filtered_meetings = [
                        m
                        for m in meetings
                        if search_term.lower() in m.get("title", "").lower()
                    ]

                # 안전한 슬라이싱을 위해 리스트 확인
                display_meetings = (
                    filtered_meetings[:10]
                    if isinstance(filtered_meetings, list)
                    else []
                )

                for meeting in display_meetings:  # 최근 10개만 표시
                    # 날짜 형식 개선
                    created_at = meeting.get("created_at", "N/A")
                    try:
                        from datetime import datetime

                        if created_at != "N/A":
                            dt = datetime.fromisoformat(
                                created_at.replace("Z", "+00:00")
                            )
                            formatted_date = dt.strftime("%m/%d")
                        else:
                            formatted_date = "N/A"
                    except:
                        formatted_date = "N/A"

                    with st.expander(
                        f"📅 {formatted_date} - {meeting.get('title', 'Untitled Meeting')}"
                    ):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            # 회의 요약 JSON 파싱
                            summary_json = meeting.get("summary", "{}")
                            try:
                                if isinstance(summary_json, str):
                                    import json

                                    summary_data = json.loads(summary_json)
                                else:
                                    summary_data = summary_json
                            except:
                                summary_data = {}

                            # 참석자 정보 처리
                            participants = summary_data.get("participants", [])
                            if not participants and "participants" in str(summary_data):
                                # 원본 텍스트에서 참석자 정보 추출 시도
                                raw_text = meeting.get("raw_text", "")
                                if "참석자:" in raw_text:
                                    lines = raw_text.split("\n")
                                    for line in lines:
                                        if "참석자:" in line:
                                            participant_info = line.split("참석자:")[
                                                1
                                            ].strip()
                                            st.write(f"**참석자:** {participant_info}")
                                            break
                                else:
                                    st.write("**참석자:** 정보 없음")
                            else:
                                if isinstance(participants, list) and participants:
                                    participants_str = ", ".join(participants)
                                    st.write(f"**참석자:** {participants_str}")
                                else:
                                    st.write("**참석자:** 정보 없음")

                            # 요약 정보 처리 (JSON 대신 실제 요약 표시)
                            if summary_data and summary_data.get("summary"):
                                summary_text = summary_data.get("summary")
                                if len(summary_text) > 100:
                                    summary_text = summary_text[:100] + "..."
                                st.write(f"**요약:** {summary_text}")
                            else:
                                st.write("**요약:** 요약 정보 없음")

                            # 액션 아이템 개수 표시 (실제 DB에서 조회)
                            try:
                                meeting_id = meeting.get("id")
                                if meeting_id:
                                    action_items = service_manager.get_action_items(
                                        meeting_id
                                    )
                                    if action_items:
                                        completed = len(
                                            [
                                                item
                                                for item in action_items
                                                if item.get("status") == "완료"
                                            ]
                                        )
                                        total = len(action_items)
                                        st.write(
                                            f"**액션 아이템:** {total}개 (완료: {completed}개)"
                                        )
                                    else:
                                        st.write("**액션 아이템:** 없음")
                                else:
                                    st.write("**액션 아이템:** 정보 없음")
                            except:
                                st.write("**액션 아이템:** 조회 실패")

                        with col2:
                            if st.button(
                                "📖 상세보기", key=f"detail_{meeting.get('id', '')}"
                            ):
                                st.session_state.selected_meeting = meeting
                                st.rerun()

        except Exception as e:
            st.error(f"❌ 회의록을 불러오는 중 오류가 발생했습니다: {str(e)}")


def render_meeting_detail(service_manager):
    """회의록 상세보기 렌더링"""
    meeting = st.session_state.selected_meeting

    # 뒤로가기 버튼
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("← 뒤로가기"):
            st.session_state.selected_meeting = None
            st.rerun()
    with col2:
        st.markdown(f"### 📋 {meeting.get('title', 'Untitled Meeting')}")

    st.markdown("---")

    # 회의 요약 JSON 파싱
    summary_json = meeting.get("summary", "{}")
    try:
        if isinstance(summary_json, str):
            import json

            summary_data = json.loads(summary_json)
        else:
            summary_data = summary_json
    except:
        summary_data = {}

    # 기본 정보
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**📅 회의 날짜**")
            created_at = meeting.get("created_at", "N/A")
            # ISO 형식 날짜를 사람이 읽기 쉬운 형태로 변환
            try:
                from datetime import datetime

                if created_at != "N/A":
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    formatted_date = dt.strftime("%Y년 %m월 %d일 %H:%M")
                else:
                    formatted_date = "날짜 정보 없음"
            except:
                formatted_date = created_at
            st.write(formatted_date)

            st.markdown("**👥 참석자**")
            # summary에서 참석자 정보 추출 시도
            participants = summary_data.get("participants", [])
            if not participants and "participants" in str(summary_data):
                # 원본 텍스트에서 참석자 정보 추출 시도
                raw_text = meeting.get("raw_text", "")
                if "참석자:" in raw_text:
                    lines = raw_text.split("\n")
                    for line in lines:
                        if "참석자:" in line:
                            participant_info = line.split("참석자:")[1].strip()
                            st.write(participant_info)
                            break
                else:
                    st.write("참석자 정보 없음")
            else:
                if isinstance(participants, list) and participants:
                    for participant in participants:
                        st.write(f"• {participant}")
                else:
                    st.write("참석자 정보 없음")

        with col2:
            st.markdown("**🏷️ 회의 ID**")
            st.code(meeting.get("id", "N/A"))

            st.markdown("**⏰ 생성일시**")
            st.write(formatted_date)

    # 회의 요약
    st.markdown("---")
    st.markdown("### 📝 회의 요약")

    # JSON 대신 읽기 쉬운 형태로 표시
    if summary_data:
        if summary_data.get("summary"):
            st.markdown(summary_data.get("summary"))
        else:
            # 전체 JSON을 보기 좋게 표시
            st.json(summary_data)
    else:
        st.write("회의 요약 정보가 없습니다.")

    # 액션 아이템 (DB에서 실제 데이터 조회)
    st.markdown("---")
    st.markdown("### ✅ 액션 아이템")

    try:
        meeting_id = meeting.get("id")
        action_items = (
            service_manager.get_action_items(meeting_id) if meeting_id else []
        )

        if action_items and isinstance(action_items, list):
            for i, item in enumerate(action_items, 1):
                with st.expander(
                    f"📌 액션 아이템 {i}: {item.get('description', 'N/A')[:50]}..."
                ):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown("**📝 설명**")
                        st.write(item.get("description", "N/A"))

                        st.markdown("**👤 추천 담당자**")
                        st.write(item.get("recommendedAssigneeId", "N/A"))

                        if item.get("finalAssigneeId"):
                            st.markdown("**👤 최종 담당자**")
                            st.write(item.get("finalAssigneeId"))

                        st.markdown("**📅 마감일**")
                        st.write(item.get("dueDate", "N/A"))

                        st.markdown("**📊 현재 상태**")
                        status = item.get("status", "미시작")
                        if status == "완료":
                            st.success(f"✅ {status}")
                        elif status == "진행중":
                            st.info(f"⏳ {status}")
                        else:
                            st.warning(f"📋 {status}")

                    with col2:
                        st.markdown("**승인 상태**")
                        approved = item.get("approved", False)
                        if approved:
                            st.success("✅ 승인됨")
                        else:
                            st.warning("⏳ 승인 대기")

                        # 상태 변경 버튼
                        current_status = item.get("status", "미시작")

                        if st.button(
                            "상태 변경", key=f"status_change_{item.get('id', i)}"
                        ):
                            # 상태 변경 옵션
                            new_status = st.selectbox(
                                "새로운 상태 선택:",
                                ["미시작", "진행중", "완료"],
                                index=(
                                    ["미시작", "진행중", "완료"].index(current_status)
                                    if current_status in ["미시작", "진행중", "완료"]
                                    else 0
                                ),
                                key=f"status_select_{item.get('id', i)}",
                            )

                            if st.button(
                                "변경 확인", key=f"confirm_change_{item.get('id', i)}"
                            ):
                                try:
                                    item_id = item.get("id")
                                    success = service_manager.update_action_item_status(
                                        item_id, meeting_id, new_status
                                    )
                                    if success:
                                        st.success(
                                            f"상태가 '{new_status}'로 변경되었습니다!"
                                        )
                                        st.rerun()
                                    else:
                                        st.error("상태 변경에 실패했습니다.")
                                except Exception as e:
                                    st.error(f"상태 변경 실패: {str(e)}")
        else:
            st.info("액션 아이템이 없습니다.")
    except Exception as e:
        st.error(f"액션 아이템 조회 중 오류 발생: {str(e)}")
        st.info("액션 아이템이 없습니다.")

    # 원본 텍스트 (있는 경우)
    if meeting.get("raw_text"):
        st.markdown("---")
        st.markdown("### 📄 원본 텍스트")
        with st.expander("원본 회의 내용 보기"):
            st.text_area(
                "원본 텍스트",
                value=meeting.get("raw_text", ""),
                height=300,
                disabled=True,
            )

    # 수정 및 삭제 옵션
    st.markdown("---")
    st.markdown("### ⚙️ 관리 옵션")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("✏️ 수정", use_container_width=True):
            st.info("수정 기능은 향후 구현될 예정입니다.")

    with col2:
        if st.button("📤 내보내기", use_container_width=True):
            # JSON 형태로 회의록 내보내기
            import json

            json_str = json.dumps(meeting, ensure_ascii=False, indent=2)
            st.download_button(
                label="💾 JSON 다운로드",
                data=json_str,
                file_name=f"meeting_{meeting.get('id', 'unknown')}.json",
                mime="application/json",
            )

    with col3:
        if st.button("🗑️ 삭제", use_container_width=True):
            st.error("삭제 기능은 향후 구현될 예정입니다.")
