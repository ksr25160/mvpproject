"""
Meeting AI Assistant - 메인 애플리케이션
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import uuid
from datetime import datetime

# 환경 설정 및 로깅 시스템
from config.environment import get_config
from config.logging_config import setup_logger, get_logger

# 통합 서비스 매니저 사용 (일관성 개선)
from services.service_manager import ServiceManager

# 페이지 모듈들을 직접 import (app 디렉토리를 Python 경로에 추가)
sys.path.append(str(Path(__file__).parent))
from components.chat_page import render_chatbot
from components.meeting_records_page import render_meeting_records
from components.task_management_page import render_task_management
from components.staff_management_page import render_staff_management
from utils.chat_utils import (
    initialize_chat_session,
    load_chat_history_from_db,
)

# 환경 설정 및 로깅 초기화
config = get_config()
setup_logger()
logger = get_logger(__name__)

# 서비스 매니저 초기화
service_manager = ServiceManager()

# 세션 상태 초기화 - 각 항목을 개별적으로 확인
if "session_id" not in st.session_state:
    initialize_chat_session()
    logger.log_user_action("session_started", st.session_state.session_id)

if "current_page" not in st.session_state:
    st.session_state.current_page = "Chat"

# chat_messages와 chat_history는 initialize_chat_session에서 처리됨

if "processing" not in st.session_state:
    st.session_state.processing = False

# 현재 채팅의 DB ID 초기화 (없으면 None)
if "current_chat_db_id" not in st.session_state:
    st.session_state.current_chat_db_id = None

# 페이지 설정
st.set_page_config(
    page_title="Meeting AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


def render_sidebar():
    """왼쪽 사이드바 렌더링 (메뉴 + 채팅 히스토리)"""
    with st.sidebar:  # 메뉴 섹션
        with st.container():
            st.markdown("**📋 메뉴**")

            # 메뉴 버튼들
            menu_options = [
                "채팅",
                "회의 기록",
                "업무 관리",
                "직원 관리",
            ]

            # 한글명과 영문명 매핑
            menu_mapping = {
                "채팅": "Chat",
                "회의 기록": "Meeting Records",
                "업무 관리": "Task Management",
                "직원 관리": "Staff Management",
            }

            # 현재 페이지의 한글명 찾기
            current_page_korean = None
            for korean, english in menu_mapping.items():
                if english == st.session_state.current_page:
                    current_page_korean = korean
                    break

            for option in menu_options:
                if st.button(
                    option,
                    key=f"menu_{option}",
                    use_container_width=True,
                    type=("primary" if option == current_page_korean else "secondary"),
                ):
                    st.session_state.current_page = menu_mapping[option]
                    st.rerun()

        st.divider()

        # 채팅 히스토리 섹션 (Chat 페이지에서만 표시)
        if st.session_state.current_page == "Chat":
            with st.container():
                st.markdown("**💬 채팅**")

                # 새로운 채팅 버튼
                if st.button("새로운 채팅", use_container_width=True):
                    initialize_chat_session()
                    st.rerun()

                # 간단한 검색 기능
                search_term = st.text_input(
                    "🔍 채팅 검색", placeholder="검색어 입력...", key="chat_search"
                )

                # DB에서 채팅 히스토리 로드 (단일 사용자이므로 모든 히스토리 표시)
                try:
                    with st.spinner("채팅 히스토리 로딩 중..."):
                        db_chat_histories = service_manager.get_chat_histories(
                            session_id=None, limit=30
                        )

                    # 검색 필터링
                    if search_term and db_chat_histories:
                        db_chat_histories = [
                            chat
                            for chat in db_chat_histories
                            if search_term.lower() in chat.get("summary", "").lower()
                        ]

                    if db_chat_histories:
                        st.caption(f"💬 총 {len(db_chat_histories)}개의 채팅 히스토리")

                        # DB에서 로드한 채팅 히스토리 표시
                        for i, chat_history in enumerate(db_chat_histories):
                            try:
                                timestamp = (
                                    datetime.fromisoformat(
                                        chat_history.get("timestamp", "")
                                    ).strftime("%m-%d %H:%M")
                                    if chat_history.get("timestamp")
                                    else "시간 정보 없음"
                                )
                            except:
                                timestamp = "시간 정보 없음"

                            summary = (
                                chat_history.get("summary", "대화 내용 없음")[:30]
                                + "..."
                            )
                            message_count = chat_history.get("message_count", 0)

                            with st.expander(
                                f"🕒 {timestamp} ({message_count}개 메시지)",
                                expanded=False,
                            ):
                                st.caption(summary)
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.button(
                                        "불러오기",
                                        key=f"load_db_chat_{i}",
                                        use_container_width=True,
                                    ):
                                        with st.spinner("채팅 히스토리 불러오는 중..."):
                                            if load_chat_history_from_db(
                                                chat_history.get("id"), service_manager
                                            ):
                                                st.success(
                                                    "채팅 히스토리를 불러왔습니다!"
                                                )
                                                st.rerun()
                                            else:
                                                st.error("불러오기에 실패했습니다.")
                                with col2:
                                    if st.button(
                                        "삭제",
                                        key=f"delete_db_chat_{i}",
                                        use_container_width=True,
                                    ):
                                        with st.spinner("삭제 중..."):
                                            if service_manager.delete_chat_history(
                                                chat_history.get("id")
                                            ):
                                                st.success("삭제되었습니다!")
                                                st.rerun()
                                            else:
                                                st.error("삭제 실패")
                    else:
                        if search_term:
                            st.caption(f"*'{search_term}' 검색 결과가 없습니다*")
                        else:
                            st.caption("*아직 채팅 기록이 없습니다*")

                except Exception as e:
                    st.error(f"채팅 히스토리 로드 오류: {str(e)}")
                    # 폴백: 세션 상태의 채팅 히스토리 사용
                    if st.session_state.chat_history:
                        for i, chat in enumerate(
                            reversed(st.session_state.chat_history[-5:])
                        ):
                            timestamp = chat.get("timestamp", "시간 정보 없음")
                            preview = chat.get("preview", "대화 내용 없음")[:30] + "..."

                            with st.expander(f"🕒 {timestamp}", expanded=False):
                                st.caption(preview)
                                if st.button(
                                    "불러오기",
                                    key=f"load_session_chat_{i}",
                                    use_container_width=True,
                                ):
                                    st.session_state.chat_messages = chat.get(
                                        "messages", []
                                    )
                                    st.rerun()
                    else:
                        st.caption("*아직 채팅 기록이 없습니다*")


def main():
    """메인 애플리케이션"""
    try:
        logger.info("애플리케이션 시작")
        print("🚀 Meeting AI Assistant 시작")

        # 레이아웃: 사이드바 + 메인 콘텐츠 + 챗봇
        # Streamlit의 기본 사이드바 사용 + 메인 영역을 2개 컬럼으로 분할

        # 사이드바 렌더링
        render_sidebar()
        # Chat 페이지일 때는 챗봇만 전체 너비로 표시
        if st.session_state.current_page == "Chat":
            render_chatbot(service_manager, fullwidth=True)
        else:
            # 다른 페이지에서는 챗봇 없이 메인 콘텐츠만 전체 너비로 표시
            # 현재 페이지에 따른 콘텐츠 렌더링
            if st.session_state.current_page == "Meeting Records":
                render_meeting_records(service_manager)
            elif st.session_state.current_page == "Task Management":
                render_task_management(service_manager)
            elif st.session_state.current_page == "Staff Management":
                render_staff_management(service_manager)
        # 데이터베이스 초기화 (첫 실행시에만)
        if "db_initialized" not in st.session_state:
            logger.info("데이터베이스 초기화 중...")
            print("💾 데이터베이스 초기화 중...")
            # ServiceManager 초기화 시에 이미 init_cosmos()가 호출됨
            st.session_state.db_initialized = True
            logger.info("데이터베이스 초기화 완료")
            print("✅ 데이터베이스 초기화 완료")

        # RAG용 직원 데이터 인덱스 분리 및 재구성 (첫 실행시에만)
        if "staff_indexed" not in st.session_state:
            logger.info("직원 전용 인덱스 구성 및 데이터 이전 중...")
            print("👥 직원 전용 인덱스 구성 및 데이터 이전 중...")
            try:
                # 1. 직원 전용 인덱스 생성 확인
                from services.search_service import (
                    create_search_index,
                    clean_legacy_staff_data_from_meetings_index,
                )

                print("🔧 인덱스 생성 확인 중...")
                create_search_index()

                # 2. 기존 혼합 인덱스에서 직원 데이터 제거
                print("🗑️ 기존 인덱스에서 직원 데이터 제거 중...")
                clean_legacy_staff_data_from_meetings_index()

                # 3. 직원 전용 인덱스에 데이터 추가
                print("📝 직원 전용 인덱스에 데이터 추가 중...")
                if service_manager.index_staff_data_for_search():
                    st.session_state.staff_indexed = True
                    logger.info("직원 전용 인덱스 구성 완료")
                    print("✅ 직원 전용 인덱스 구성 완료")
                else:
                    logger.warning("직원 데이터 인덱싱 실패")
                    print("⚠️ 직원 데이터 인덱싱 실패")
            except Exception as e:
                logger.error(f"직원 인덱스 구성 오류: {e}")
                print(f"❌ 직원 인덱스 구성 오류: {e}")

        # 채팅 히스토리 자동 저장 (5개 메시지마다)
        if (
            len(st.session_state.chat_messages) >= 5
            and len(st.session_state.chat_messages) % 5 == 0
        ):
            if (
                "last_saved_count" not in st.session_state
                or st.session_state.last_saved_count
                != len(st.session_state.chat_messages)
            ):
                try:
                    session_id = st.session_state.get("session_id", "unknown")
                    messages = st.session_state.chat_messages

                    # 첫 번째 사용자 메시지를 요약으로 사용
                    user_messages = [
                        msg for msg in messages if msg.get("role") == "user"
                    ]
                    summary = (
                        user_messages[0].get("content", "New Chat")[:50]
                        if user_messages
                        else "New Chat"
                    )

                    chat_id = service_manager.save_chat_history(
                        session_id, messages, summary
                    )
                    if chat_id:
                        st.session_state.last_saved_count = len(
                            st.session_state.chat_messages
                        )
                        print(f"✅ 자동 채팅 저장 완료: {chat_id}")
                except Exception as e:
                    print(f"❌ 자동 채팅 저장 오류: {str(e)}")

    except Exception as e:
        error_details = {
            "session_id": st.session_state.get("session_id", "unknown"),
            "current_page": st.session_state.get("current_page", "unknown"),
            "error_type": type(e).__name__,
        }
        logger.log_error_with_context("메인 애플리케이션 오류", e, error_details)
        print(f"❌ 메인 애플리케이션 치명적 오류: {type(e).__name__}: {str(e)}")

        # 사용자에게 상세한 에러 메시지 표시
        st.error(
            f"""
        ❌ **애플리케이션 오류가 발생했습니다**
        
        **오류 유형:** {type(e).__name__}
        **오류 내용:** {str(e)}
        **세션 ID:** {st.session_state.get('session_id', 'N/A')}
        
        페이지를 새로고침하거나 관리자에게 문의해주세요.
        """
        )

        # 기본 복구 시도
        try:
            st.info("🔄 자동 복구를 시도합니다...")
            # 세션 상태 초기화
            for key in ["chat_messages", "chat_history", "processing"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        except:
            st.error("자동 복구에 실패했습니다. 페이지를 새로고침해주세요.")


if __name__ == "__main__":
    main()
