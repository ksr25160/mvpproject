"""
Meeting AI Assistant - 채팅 처리 유틸리티
"""

import streamlit as st
import json
import re
from datetime import datetime


def process_chat_message(user_input, service_manager):
    """채팅 메시지 처리"""
    try:
        # 사용자 메시지 추가
        st.session_state.chat_messages.append({"role": "user", "content": user_input})

        # 처리 상태 설정
        st.session_state.processing = True

        # 간단한 키워드 기반 응답 (더 구체적인 키워드부터 체크)
        response = ""

        # 미할당 관련 키워드 우선 체크
        if any(
            keyword in user_input.lower()
            for keyword in ["미할당", "unassigned", "담당자 없는"]
        ):
            response = _handle_staff_query(user_input, service_manager)
        # 담당자 지정 관련 키워드 체크
        elif (
            any(keyword in user_input.lower() for keyword in ["지정", "할당", "assign"])
            and "담당자" in user_input.lower()
        ):
            response = _handle_staff_query(user_input, service_manager)
        # 회의 관련 키워드
        elif any(
            keyword in user_input.lower() for keyword in ["회의", "미팅", "회의록"]
        ):
            response = _handle_meeting_query(user_input, service_manager)
        # 작업 관련 키워드
        elif any(
            keyword in user_input.lower()
            for keyword in ["작업", "업무", "할일", "todo", "task"]
        ):
            response = _handle_task_query(user_input, service_manager)
        # 검색 관련 키워드
        elif any(
            keyword in user_input.lower() for keyword in ["검색", "search", "찾기"]
        ):
            response = _handle_search_query(user_input)
        # 수정 관련 키워드
        elif any(
            keyword in user_input.lower()
            for keyword in ["수정", "변경", "업데이트", "modify", "update", "change"]
        ):
            response = _handle_modification_query(user_input, service_manager)
        # 직원 관련 키워드
        elif any(
            keyword in user_input.lower()
            for keyword in ["직원", "인사", "사람", "staff", "담당자", "추천"]
        ):
            response = _handle_staff_query(user_input, service_manager)
        else:
            # 일반적인 질문은 검색 기반 OpenAI로 처리
            try:
                response = service_manager.ask_question_with_search(user_input)

                # 검색 결과가 없는 경우 기본 도움말 제공
                if "관련 회의록을 찾을 수 없습니다" in response:
                    response = _handle_general_help()

            except Exception as e:
                response = _handle_general_help()

        # AI 응답 추가
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": response}
        )

        # 채팅 히스토리에 추가
        add_to_chat_history(user_input, response, service_manager)

        return response  # 응답 반환 추가

    except Exception as e:
        error_response = f"❌ 질문 처리 중 오류가 발생했습니다: {str(e)}"
        print(f"❌ 질문 처리 오류: {str(e)}")

        st.session_state.chat_messages.append(
            {"role": "assistant", "content": error_response}
        )

        return error_response  # 오류 응답도 반환

    finally:
        # 처리 상태 해제
        st.session_state.processing = False
        st.rerun()


def _handle_meeting_query(user_input, service_manager):
    """회의 관련 질문 처리"""
    meetings = service_manager.get_meetings()
    if meetings:
        response = f"""📝 **회의록 관련 정보**

현재 저장된 회의록: {len(meetings)}개

최근 회의록:
"""
        for i, meeting in enumerate(meetings[:3], 1):
            response += f"\n{i}. {meeting.get('title', 'N/A')} ({meeting.get('created_at', 'N/A')})"

        if len(meetings) > 3:
            response += f"\n... 외 {len(meetings) - 3}개"

        response += "\n\n📋 Meeting Records 페이지에서 자세한 내용을 확인하세요."
    else:
        response = "📝 아직 저장된 회의록이 없습니다. 음성 파일이나 텍스트를 업로드하여 회의록을 생성해보세요!"

    return response


def _handle_task_query(user_input, service_manager):
    """작업 관련 질문 처리"""
    try:
        # 새로운 작업 추가 요청 인식
        if any(
            keyword in user_input.lower()
            for keyword in ["추가", "새로운", "만들", "생성", "add", "create", "new"]
        ):
            return _handle_task_creation(user_input, service_manager)

        # 작업 상태 변경 요청 인식
        elif any(
            keyword in user_input.lower()
            for keyword in [
                "완료",
                "변경",
                "상태",
                "수정",
                "complete",
                "change",
                "update",
            ]
        ):
            return _handle_task_status_update(user_input, service_manager)

        # 기존 작업 조회 기능
        else:
            meetings = service_manager.get_meetings()
            all_action_items = []
            unassigned_count = 0

            for meeting in meetings:
                meeting_id = meeting.get("id")
                if meeting_id:
                    action_items = service_manager.get_action_items(meeting_id)
                    for item in action_items:
                        # 미할당 카운트
                        assignee = item.get("recommendedAssigneeId") or item.get(
                            "assignee"
                        )
                        if not assignee or assignee.lower() in [
                            "미할당",
                            "unassigned",
                            "",
                            "없음",
                        ]:
                            unassigned_count += 1
                        all_action_items.append(item)

            if all_action_items:
                completed = len(
                    [item for item in all_action_items if item.get("status") == "완료"]
                )
                pending = len(all_action_items) - completed

                response = f"""✅ **작업 현황**

전체 작업: {len(all_action_items)}개
완료: {completed}개
대기중: {pending}개
미할당: {unassigned_count}개

최근 작업:
"""
                for i, task in enumerate(all_action_items[:5], 1):
                    status = "✅" if task.get("status") == "완료" else "⏳"
                    assignee = (
                        task.get("recommendedAssigneeId")
                        or task.get("assignee")
                        or "미할당"
                    )
                    response += f"{i}. {status} **{task.get('description', 'N/A')}**\n"
                    response += f"   └ 담당자: {assignee}\n\n"

                if unassigned_count > 0:
                    response += f"💡 '미할당 작업 보여줘' 명령으로 미할당 작업을 확인할 수 있습니다.\n"

                response += "📋 Task Management 페이지에서 자세한 내용을 확인하세요."
            else:
                response = "✅ 등록된 작업이 없습니다. 회의를 분석하면 자동으로 액션 아이템이 생성됩니다!"

    except Exception as e:
        response = f"❌ 작업 정보를 가져오는 중 오류가 발생했습니다: {str(e)}"

    return response


def _handle_task_creation(user_input, service_manager):
    """새로운 작업 추가 처리"""
    try:
        import re
        from datetime import datetime, timedelta

        # 작업 설명 추출
        task_description = ""
        assignee_name = None
        due_date = None

        # 정규식으로 패턴 매칭
        # "새로운 작업 추가해줘: 데이터베이스 백업, 담당자는 한성민, 마감일은 내일"

        # 작업 내용 추출
        task_patterns = [
            r"추가해줘:?\s*([^,]+)",
            r"작업:?\s*([^,]+)",
            r"업무:?\s*([^,]+)",
            r"할일:?\s*([^,]+)",
        ]

        for pattern in task_patterns:
            match = re.search(pattern, user_input)
            if match:
                task_description = match.group(1).strip()
                break

        # 담당자 추출
        assignee_patterns = [
            r"담당자(?:는|는)?\s*([^,\s]+)",
            r"담당자:?\s*([^,\s]+)",
            r"assignee:?\s*([^,\s]+)",
        ]

        for pattern in assignee_patterns:
            match = re.search(pattern, user_input)
            if match:
                assignee_name = match.group(1).strip()
                break

        # 마감일 추출
        if "내일" in user_input:
            due_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "모레" in user_input:
            due_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        elif "다음주" in user_input:
            due_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        else:
            # 날짜 패턴 추출 시도
            date_patterns = [
                r"마감일(?:은|는)?\s*(\d{4}-\d{2}-\d{2})",
                r"(\d{1,2}/\d{1,2})",
                r"(\d{1,2}월\s*\d{1,2}일)",
            ]

            for pattern in date_patterns:
                match = re.search(pattern, user_input)
                if match:
                    date_str = match.group(1)
                    # 간단한 날짜 변환 (실제로는 더 정교한 파싱 필요)
                    try:
                        if "/" in date_str:
                            month, day = date_str.split("/")
                            current_year = datetime.now().year
                            due_date = f"{current_year}-{int(month):02d}-{int(day):02d}"
                        # 다른 형식들도 필요에 따라 추가
                    except:
                        pass
                    break

        # 작업 설명이 없으면 오류
        if not task_description:
            return "❌ 작업 내용을 명확히 입력해주세요.\n예시: '새로운 작업 추가해줘: 데이터베이스 백업, 담당자는 한성민, 마감일은 내일'"

        # 담당자 이름이 있으면 유효성 확인
        if assignee_name:
            staff = service_manager.find_staff_by_name(assignee_name)
            if not staff:
                # 담당자를 찾을 수 없으면 추천 시스템 사용
                recommended_staff = service_manager.recommend_assignee_for_task(
                    task_description
                )
                if recommended_staff:
                    assignee_name = recommended_staff.get("name", "미할당")
                else:
                    assignee_name = "미할당"

        # 새로운 액션 아이템 추가
        item_id = service_manager.add_new_action_item(
            task_description, assignee_name, due_date
        )

        if item_id:
            response = f"""✅ **새로운 작업이 추가되었습니다!**

📋 **작업 내용**: {task_description}
👤 **담당자**: {assignee_name or '미할당'}
📅 **마감일**: {due_date or '1주일 후'}
🆔 **작업 ID**: {item_id}

📋 Task Management 페이지에서 자세한 관리가 가능합니다."""
        else:
            response = "❌ 작업 추가 중 오류가 발생했습니다."

    except Exception as e:
        response = f"❌ 작업 추가 중 오류가 발생했습니다: {str(e)}"

    return response


def _handle_task_status_update(user_input, service_manager):
    """작업 상태 업데이트 처리"""
    try:
        # 모든 액션 아이템 조회
        all_action_items = service_manager.get_all_action_items()

        if not all_action_items:
            return "❌ 업데이트할 작업이 없습니다."

        # 간단한 키워드 매칭으로 작업 찾기
        user_input_lower = user_input.lower()
        matched_items = []

        for item in all_action_items:
            description = item.get("description", "").lower()
            assignee = item.get("recommendedAssigneeId", "").lower()

            # 작업 설명이나 담당자가 사용자 입력에 포함되어 있으면 매칭
            if any(
                word in description
                for word in user_input_lower.split()
                if len(word) > 2
            ):
                matched_items.append(item)
            elif assignee and assignee in user_input_lower:
                matched_items.append(item)

        if not matched_items:
            return (
                f"❌ 해당하는 작업을 찾을 수 없습니다.\n\n현재 작업 목록:\n"
                + "\n".join(
                    [
                        f"- {item.get('description', 'N/A')}"
                        for item in all_action_items[:5]
                    ]
                )
            )

        # 첫 번째 매칭된 항목 업데이트
        item = matched_items[0]
        item_id = item.get("id")
        meeting_id = item.get("meetingId")

        # 상태 결정
        new_status = "완료" if "완료" in user_input_lower else "진행중"

        # 상태 업데이트
        try:
            service_manager.update_action_item_status(item_id, meeting_id, new_status)

            response = f"""✅ **작업 상태가 업데이트되었습니다!**

📋 **작업**: {item.get('description', 'N/A')}
👤 **담당자**: {item.get('recommendedAssigneeId', 'N/A')}
🔄 **상태**: {item.get('status', '미시작')} → {new_status}

📋 Task Management 페이지에서 확인하세요."""

        except Exception as e:
            response = f"❌ 작업 상태 업데이트 실패: {str(e)}"

    except Exception as e:
        response = f"❌ 작업 상태 업데이트 중 오류가 발생했습니다: {str(e)}"

    return response


def _handle_search_query(user_input):
    """검색 관련 질문 처리"""
    try:
        # AI Search 기능 사용
        from services.search_service import search_documents

        search_results = search_documents(user_input, top=3)
        if search_results:
            response = f"""🔍 **검색 결과**

"{user_input}"에 대한 검색 결과:

"""
            for i, result in enumerate(search_results, 1):
                response += f"{i}. {result.get('content', 'N/A')[:100]}...\n\n"
        else:
            response = "🔍 검색 결과가 없습니다. 다른 키워드로 시도해보세요."
    except:
        response = "🔍 검색 기능은 현재 준비 중입니다."

    return response


def _handle_modification_query(user_input, service_manager):
    """자연어 수정 기능 처리"""
    try:
        meetings = service_manager.get_meetings()

        if not meetings:
            return "❌ 수정할 회의록이 없습니다. 먼저 회의록을 생성해주세요."

        # 간단한 매칭 (첫 번째 회의를 대상으로)
        target_meeting = meetings[0]
        meeting_id = target_meeting.get("id")
        original_summary = target_meeting.get("summary_json", {})

        # OpenAI로 자연어 수정 요청
        print(f"🔧 자연어 수정 요청: {user_input}")
        modified_result = service_manager.apply_json_modification(
            (
                json.dumps(original_summary)
                if isinstance(original_summary, dict)
                else str(original_summary)
            ),
            user_input,
        )

        response = f"""✅ **자연어 수정 완료**

**회의:** {target_meeting.get('title', 'N/A')}
**수정 요청:** {user_input}

💡 수정사항이 적용되었습니다. Meeting Records에서 확인하세요.
"""

    except Exception as e:
        response = f"❌ 자연어 수정 중 오류가 발생했습니다: {str(e)}"

    return response


def _handle_staff_query(user_input, service_manager):
    """인사정보 관련 질문 처리"""
    try:
        staff_list = service_manager.get_all_staff()
        staff_count = len(staff_list)

        # 미할당 작업 조회 (가장 먼저 체크)
        if any(
            keyword in user_input.lower()
            for keyword in ["미할당", "unassigned", "담당자 없는"]
        ):
            return _handle_unassigned_tasks_query(user_input, service_manager)

        # 담당자 지정 요청 처리 (두 번째로 체크)
        elif (
            any(keyword in user_input.lower() for keyword in ["지정", "할당", "assign"])
            and "담당자" in user_input.lower()
        ):
            return _handle_assignee_assignment(user_input, service_manager)

        # 부서별 직원 조회
        elif any(
            dept in user_input.lower()
            for dept in ["개발팀", "개발", "dev", "마케팅", "디자인", "인프라", "영업"]
        ):
            department = None
            if "개발" in user_input.lower():
                department = "개발팀"
            elif "마케팅" in user_input.lower():
                department = "마케팅팀"
            elif "디자인" in user_input.lower():
                department = "디자인팀"
            elif "인프라" in user_input.lower():
                department = "인프라팀"
            elif "영업" in user_input.lower():
                department = "영업팀"

            if department:
                dept_staff = [
                    staff
                    for staff in staff_list
                    if staff.get("department") == department
                ]
                if dept_staff:
                    response = f"👥 **{department} 직원** ({len(dept_staff)}명)\n\n"
                    for i, staff in enumerate(dept_staff, 1):
                        skills = staff.get("skills", [])
                        skill_text = (
                            ", ".join(skills[:3]) if skills else "스킬 정보 없음"
                        )
                        response += f"{i}. **{staff.get('name', 'N/A')}** ({staff.get('position', 'N/A')})\n"
                        response += f"   └ 스킬: {skill_text}\n\n"
                    return response
                else:
                    return f"❌ {department}에 등록된 직원이 없습니다."

        # 전체 직원 목록 조회
        elif any(
            keyword in user_input.lower()
            for keyword in ["목록", "list", "전체", "모든", "모두"]
        ):
            if staff_list:
                response = f"👥 **직원 목록** ({staff_count}명)\n\n"
                for i, staff in enumerate(staff_list[:8], 1):
                    response += f"{i}. **{staff.get('name', 'N/A')}** ({staff.get('department', 'N/A')})\n"
                    response += f"   └ {staff.get('position', 'N/A')} | {staff.get('email', 'N/A')}\n\n"

                if len(staff_list) > 8:
                    response += f"... 외 {len(staff_list) - 8}명\n\n"

                response += "📋 Staff Management 페이지에서 상세 정보를 확인하고 관리할 수 있습니다."
                return response
            else:
                return "👥 등록된 직원이 없습니다. Staff Management에서 직원을 추가해보세요!"

        # 담당자 추천 요청
        elif any(
            keyword in user_input.lower()
            for keyword in ["추천", "recommend", "적합한", "맞는"]
        ):
            # 작업 키워드 추출
            task_keywords = user_input.lower()
            recommended_staff = service_manager.recommend_assignee_for_task(
                task_keywords
            )
            if recommended_staff:
                response = f"""🎯 **담당자 추천**

**추천 담당자**: {recommended_staff.get('name', 'N/A')}
**부서**: {recommended_staff.get('department', 'N/A')}
**직급**: {recommended_staff.get('position', 'N/A')}
**관련 스킬**: {', '.join(recommended_staff.get('skills', [])[:3])}

💡 이 담당자가 해당 작업에 적합합니다."""
                return response
            else:
                return (
                    "❌ 적합한 담당자를 찾을 수 없습니다. 다른 키워드로 시도해보세요."
                )

        # 기본 도움말
        else:
            response = f"""👥 **인사정보 관리**

현재 등록된 직원: **{staff_count}명**

**사용 가능한 명령어:**
• "직원 목록 보여줘" - 전체 직원 목록 조회
• "개발팀 직원 찾아줘" - 특정 부서 직원 검색  
• "UI 디자인 담당자 추천해줘" - 작업에 적합한 담당자 추천
• "미할당 작업 보여줘" - 담당자가 없는 작업 조회
• "[작업명] 담당자를 [이름]으로 지정해줘" - 담당자 지정

📋 Staff Management 페이지에서 직원 정보를 추가/수정/삭제할 수 있습니다.
"""
            return response

    except Exception as e:
        response = f"❌ 인사정보 조회 중 오류가 발생했습니다: {str(e)}"
        return response


def _handle_general_help():
    """일반적인 도움말 응답"""
    return f"""🤖 **Meeting AI Assistant입니다**

다음과 같은 기능을 제공합니다:

📁 **파일 업로드**: 음성/문서 파일을 업로드하여 회의록 생성
📝 **회의록 관리**: 저장된 회의록 조회 및 관리  
✅ **작업 관리**: 액션 아이템 추적 및 완료 처리
👥 **인사 관리**: 직원 정보 관리 및 담당자 추천
🔍 **검색**: 회의 내용 및 문서 검색

**질문 예시:**
- "최근 회의록을 보여줘"
- "완료되지 않은 작업이 뭐가 있어?"
- "직원 목록 보여줘"
- "안녕하세요"

무엇을 도와드릴까요?
"""


def add_to_chat_history(user_message, ai_response, service_manager):
    """채팅 히스토리에 대화 추가 및 DB 저장/업데이트"""
    chat_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "preview": user_message,
        "messages": [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": ai_response},
        ],
    }

    # 세션 상태에 추가
    st.session_state.chat_history.append(chat_entry)

    # 히스토리가 너무 길어지면 오래된 것 삭제
    if len(st.session_state.chat_history) > 50:
        st.session_state.chat_history = st.session_state.chat_history[-50:]

    # DB에 저장/업데이트 (save_chat_history가 이미 내장 업데이트 로직 포함)
    try:
        session_id = st.session_state.get("session_id", "unknown")
        all_messages = st.session_state.get("chat_messages", [])

        # 대화가 있을 때만 저장 (최소 2개 이상의 메시지)
        if len(all_messages) >= 2:
            summary = (
                all_messages[0].get("content", "")[:50]
                if all_messages
                else user_message[:50]
            )
            summary = summary + "..." if len(summary) >= 50 else summary

            # save_chat_history 함수가 내부적으로 업데이트/생성을 처리
            chat_id = service_manager.save_chat_history(
                session_id, all_messages, summary
            )
            if chat_id:
                # 현재 채팅의 DB ID를 세션에 저장 (세션 기반 고정 ID이므로 항상 같음)
                st.session_state.current_chat_db_id = chat_id
                print(f"✅ 채팅 히스토리 저장/업데이트 완료: {chat_id}")
    except Exception as e:
        print(f"❌ 채팅 히스토리 저장/업데이트 오류: {str(e)}")


def initialize_chat_session():
    """새로운 채팅 세션 초기화"""
    import uuid

    # 새로운 세션 ID 생성
    st.session_state.session_id = str(uuid.uuid4())

    # 채팅 메시지 초기화
    st.session_state.chat_messages = []

    # 채팅 히스토리 초기화 (UI용)
    st.session_state.chat_history = []

    # 처리 상태 초기화
    st.session_state.processing = False

    # 현재 채팅의 DB ID 초기화 (새 채팅이므로 None)
    st.session_state.current_chat_db_id = None

    print(f"✅ 새로운 채팅 세션 초기화: {st.session_state.session_id}")


def load_chat_history_from_db(chat_id, service_manager):
    """DB에서 특정 채팅 히스토리 로드"""
    try:
        chat_data = service_manager.get_chat_history_by_id(chat_id)
        if chat_data and "messages" in chat_data:
            # 채팅 메시지 복원
            st.session_state.chat_messages = chat_data["messages"]

            # 현재 채팅의 DB ID를 설정 (이후 업데이트용)
            st.session_state.current_chat_db_id = chat_id

            # 세션 ID도 원래 채팅의 세션 ID로 복원 (선택적)
            if chat_data.get("session_id"):
                st.session_state.session_id = chat_data["session_id"]

            # UI용 히스토리도 업데이트
            st.session_state.chat_history = []
            for i in range(0, len(chat_data["messages"]), 2):
                if i + 1 < len(chat_data["messages"]):
                    user_msg = chat_data["messages"][i]
                    ai_msg = chat_data["messages"][i + 1]

                    entry = {
                        "timestamp": chat_data.get(
                            "created_at", datetime.now().strftime("%Y-%m-%d %H:%M")
                        ),
                        "preview": user_msg.get("content", "")[:50],
                        "messages": [user_msg, ai_msg],
                    }
                    st.session_state.chat_history.append(entry)

            print(f"✅ 채팅 히스토리 로드 완료: {chat_id} (DB ID 설정됨)")
            return True
    except Exception as e:
        print(f"❌ 채팅 히스토리 로드 오류: {str(e)}")
    return False


def _handle_unassigned_tasks_query(user_input, service_manager):
    """미할당 작업 조회 처리"""
    try:
        # 모든 회의에서 액션 아이템 수집
        meetings = service_manager.get_meetings()
        unassigned_tasks = []

        for meeting in meetings:
            meeting_id = meeting.get("id")
            if meeting_id:
                action_items = service_manager.get_action_items(meeting_id)
                for item in action_items:
                    assignee = item.get("recommendedAssigneeId") or item.get("assignee")
                    if not assignee or assignee.lower() in [
                        "미할당",
                        "unassigned",
                        "",
                        "없음",
                    ]:
                        unassigned_tasks.append(
                            {
                                **item,
                                "meeting_title": meeting.get(
                                    "title", "Unknown Meeting"
                                ),
                            }
                        )

        if unassigned_tasks:
            response = f"📋 **미할당 작업** ({len(unassigned_tasks)}개)\n\n"
            for i, task in enumerate(unassigned_tasks, 1):
                status_icon = "⏳" if task.get("status") != "완료" else "✅"
                response += f"{i}. {status_icon} **{task.get('description', 'N/A')}**\n"
                response += f"   └ 회의: {task.get('meeting_title', 'N/A')}\n"
                if task.get("dueDate"):
                    response += f"   └ 마감일: {task.get('dueDate')}\n"
                response += "\n"

            response += "💡 '작업명 담당자를 이름으로 지정해줘' 명령으로 담당자를 지정할 수 있습니다."
            return response
        else:
            return "✅ 모든 작업에 담당자가 할당되어 있습니다!"

    except Exception as e:
        return f"❌ 미할당 작업 조회 중 오류가 발생했습니다: {str(e)}"


def _handle_assignee_assignment(user_input, service_manager):
    """담당자 지정 처리"""
    try:
        # 담당자 지정 패턴 매칭
        # 예: "데이터베이스 백업 담당자를 한성민으로 지정해줘"
        # 예: "UI 디자인 담당자를 장윤서로 변경해줘"

        assignment_patterns = [
            r"(.+?)\s*담당자를\s*(.+?)(?:으로|로)\s*(?:지정|할당|변경)",
            r"(.+?)\s*(?:의\s*)?담당자\s*(?:를\s*)?(.+?)(?:으로|로)\s*(?:지정|할당|변경)",
            r"assign\s+(.+?)\s+to\s+(.+)",
        ]

        task_name = None
        assignee_name = None

        for pattern in assignment_patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                task_name = match.group(1).strip()
                assignee_name = match.group(2).strip()
                break

        if not task_name or not assignee_name:
            return """❌ 담당자 지정 형식이 올바르지 않습니다.

**올바른 형식:**
• "[작업명] 담당자를 [이름]으로 지정해줘"
• "[작업명] 담당자를 [이름]으로 변경해줘"

**예시:**
• "데이터베이스 백업 담당자를 한성민으로 지정해줘"
• "UI 디자인 담당자를 장윤서로 변경해줘"
"""

        # 담당자 이름 유효성 확인
        staff = service_manager.find_staff_by_name(assignee_name)
        if not staff:
            # 비슷한 이름 찾기
            all_staff = service_manager.get_all_staff()
            staff_names = [s.get("name", "") for s in all_staff]
            similar_names = [
                name
                for name in staff_names
                if assignee_name in name or name in assignee_name
            ]

            suggestion = ""
            if similar_names:
                suggestion = f"\n\n💡 혹시 다음 중 하나인가요?\n" + "\n".join(
                    [f"• {name}" for name in similar_names[:3]]
                )

            return f"❌ '{assignee_name}' 직원을 찾을 수 없습니다.{suggestion}"

        # 해당 작업 찾기
        meetings = service_manager.get_meetings()
        matched_tasks = []

        for meeting in meetings:
            meeting_id = meeting.get("id")
            if meeting_id:
                action_items = service_manager.get_action_items(meeting_id)
                for item in action_items:
                    item_desc = item.get("description", "").lower()
                    if task_name.lower() in item_desc:
                        matched_tasks.append(
                            {
                                **item,
                                "meeting_id": meeting_id,
                                "meeting_title": meeting.get(
                                    "title", "Unknown Meeting"
                                ),
                            }
                        )

        if not matched_tasks:
            return f"❌ '{task_name}' 작업을 찾을 수 없습니다.\n\n💡 '미할당 작업 보여줘' 명령으로 전체 작업 목록을 확인해보세요."

        # 첫 번째 매칭된 작업에 담당자 지정
        task = matched_tasks[0]
        task_id = task.get("id")
        meeting_id = task.get("meeting_id")

        # 담당자 업데이트
        success = service_manager.update_action_item_assignee(
            task_id, meeting_id, staff.get("name")
        )

        if success:
            response = f"""✅ **담당자가 지정되었습니다!**

📋 **작업**: {task.get('description', 'N/A')}
👤 **담당자**: {staff.get('name', 'N/A')} ({staff.get('department', 'N/A')})
📅 **마감일**: {task.get('dueDate', '미정')}
🔄 **상태**: {task.get('status', '미시작')}

📋 Task Management 페이지에서 확인하세요."""
        else:
            response = "❌ 담당자 지정에 실패했습니다. 다시 시도해주세요."

        return response

    except Exception as e:
        return f"❌ 담당자 지정 중 오류가 발생했습니다: {str(e)}"
