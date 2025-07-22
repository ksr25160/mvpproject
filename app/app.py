"""
Meeting AI Assistant - 메인 Streamlit 애플리케이션
종합적인 에러 로깅 및 성능 모니터링이 통합된 버전
"""
import sys
import os
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import json
import uuid
import time
import tempfile
from datetime import datetime
from typing import Optional, Dict, Any, List

# 환경 설정 및 로깅 시스템
from config.environment import get_config
from config.logging_config import setup_logger, get_logger

# 서비스 모듈들 - 함수 기반으로 일관성 있게 사용
from services.openai_service import transcribe_audio, summarize_and_extract, apply_json_modification, ask_question, ask_question_with_search
from services.blob_service import upload_to_blob  
from services.search_service import index_document, search_documents
from db.cosmos_db import init_cosmos, save_meeting, get_meetings, get_meeting, get_action_items, update_action_item_status

# 환경 설정 및 로깅 초기화
config = get_config()
setup_logger()
logger = get_logger(__name__)

# 세션 고유 ID 생성 (브라우저 세션별 추적)
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]
    logger.log_user_action("session_started", st.session_state.session_id)

# 페이지 설정
st.set_page_config(
    page_title=config.get("streamlit.page_title", "Meeting AI Assistant"),
    page_icon=config.get("streamlit.page_icon", "🤖"),
    layout=config.get("streamlit.layout", "wide"),
    initial_sidebar_state=config.get("streamlit.initial_sidebar_state", "expanded")
)

# CSS 스타일링
def load_custom_css():
    """커스텀 CSS 스타일 적용"""
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .feature-card {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #667eea;
        margin: 1rem 0;
    }
    .success-message {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
    }
    .error-message {
        background: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #f5c6cb;
    }
    
    /* 챗봇 관련 스타일 */
    .stChatMessage {
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .stChatMessage[data-testid="chat-message-assistant"] {
        background: #f8f9fa;
        border-radius: 10px;
        border: 1px solid #e9ecef;
    }
    
    .stChatMessage[data-testid="chat-message-user"] {
        background: #e3f2fd;
        border-radius: 10px;
        border: 1px solid #bbdefb;
    }
    
    /* 채팅 입력창 스타일 개선 */
    .stChatInput {
        border-radius: 10px;
        border: 2px solid #667eea;
    }
    
    /* 파일 업로드 아이콘 스타일 */
    .uploaded-file {
        background: #fff3cd;
        color: #856404;
        padding: 0.5rem;
        border-radius: 5px;
        border: 1px solid #ffeaa7;
        margin: 0.5rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

def initialize_services():
    """Azure 서비스 초기화"""
    start_time = time.time()
    
    try:
        # Cosmos DB 초기화
        init_cosmos()
        
        services = {
            'initialized': True,
            'cosmos_initialized': True
        }
        
        duration = time.time() - start_time
        logger.log_performance("services_initialization", duration, {
            "cosmos_initialized": True,
            "environment": config.environment.value
        })
        
        return services
        
    except Exception as e:
        duration = time.time() - start_time
        logger.log_error_with_context(
            "Failed to initialize Azure services", 
            e, 
            {
                "session_id": st.session_state.session_id,
                "duration": duration,
                "environment": config.environment.value
            }
        )
        return None

def process_uploaded_file(uploaded_file) -> Optional[str]:
    """업로드된 파일 처리"""
    start_time = time.time()
    
    try:
        logger.log_user_action("file_upload_started", st.session_state.session_id, {
            "filename": uploaded_file.name,
            "file_size": uploaded_file.size,
            "file_type": uploaded_file.type
        })
        
        # 파일 크기 검사
        max_size = config.get("file_upload.max_size_mb", 50) * 1024 * 1024
        if uploaded_file.size > max_size:
            error_msg = f"파일 크기가 너무 큽니다. 최대 {max_size // (1024*1024)}MB까지 업로드 가능합니다."
            logger.log_user_action("file_upload_failed", st.session_state.session_id, {
                "error": "file_too_large",
                "file_size": uploaded_file.size,
                "max_size": max_size
            })
            return error_msg
        
        # 파일 확장자 검사
        allowed_extensions = config.get("file_upload.allowed_extensions", [".pdf", ".docx", ".txt", ".wav", ".mp3"])
        file_extension = Path(uploaded_file.name).suffix.lower()
        if file_extension not in allowed_extensions:
            error_msg = f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(allowed_extensions)}"
            logger.log_user_action("file_upload_failed", st.session_state.session_id, {
                "error": "unsupported_format",
                "file_extension": file_extension,
                "allowed_extensions": allowed_extensions
            })
            return error_msg
        
        # Blob Storage에 업로드 (함수 직접 호출)
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as temp_file:
            temp_file.write(uploaded_file.getvalue())
            temp_file_path = temp_file.name
        
        try:
            blob_url = upload_to_blob(temp_file_path, uploaded_file.name)
            
            # 파일 내용 추출 및 처리
            if file_extension in ['.pdf', '.docx', '.txt']:
                # 문서 파일 처리
                content = extract_document_content(uploaded_file, file_extension)
                if content:
                    # 검색 인덱스에 추가 (함수 직접 호출)
                    doc_id = f"{st.session_state.session_id}_{uploaded_file.name}_{int(time.time())}"
                    metadata = {"filename": uploaded_file.name, "upload_time": datetime.now().isoformat()}
                    index_document(doc_id, content, metadata)
            elif file_extension in ['.wav', '.mp3']:
                # 오디오 파일 처리
                content = transcribe_audio(temp_file_path)
                if content:
                    # 전사된 내용을 분석
                    analysis_result = summarize_and_extract(content)
                    # Cosmos DB에 저장
                    meeting_title = f"음성 파일 분석: {uploaded_file.name}"
                    save_meeting(meeting_title, content, json.dumps(analysis_result))
        
        finally:
            # 임시 파일 삭제
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        
        duration = time.time() - start_time
        logger.log_performance("file_processing", duration, {
            "filename": uploaded_file.name,
            "file_size": uploaded_file.size,
            "file_type": uploaded_file.type,
            "blob_url": blob_url if 'blob_url' in locals() else None
        })
        
        logger.log_user_action("file_upload_completed", st.session_state.session_id, {
            "filename": uploaded_file.name,
            "blob_url": blob_url if 'blob_url' in locals() else None,
            "processing_duration": duration
        })
        
        return f"파일 '{uploaded_file.name}'이 성공적으로 업로드되고 처리되었습니다."
        
    except Exception as e:
        duration = time.time() - start_time
        logger.log_error_with_context(
            f"Failed to process uploaded file: {uploaded_file.name}",
            e,
            {
                "session_id": st.session_state.session_id,
                "filename": uploaded_file.name,
                "file_size": uploaded_file.size,
                "duration": duration
            }
        )
        return f"파일 처리 중 오류가 발생했습니다: {str(e)}"

def extract_document_content(uploaded_file, file_extension: str) -> Optional[str]:
    """문서에서 텍스트 내용 추출"""
    start_time = time.time()
    
    try:
        if file_extension == '.txt':
            content = uploaded_file.getvalue().decode('utf-8')
        else:
            # PDF, DOCX는 추후 구현 (현재는 텍스트만 지원)
            return None
        
        duration = time.time() - start_time
        logger.log_performance("document_extraction", duration, {
            "file_extension": file_extension,
            "content_length": len(content) if content else 0
        })
        
        return content.strip() if content else None
        
    except Exception as e:
        duration = time.time() - start_time
        logger.log_error_with_context(
            f"Failed to extract content from document: {file_extension}",
            e,
            {
                "session_id": st.session_state.session_id,
                "file_extension": file_extension,
                "duration": duration
            }
        )
        return None

def process_text_input(text_input: str) -> str:
    """텍스트 입력 처리 및 AI 분석"""
    start_time = time.time()
    
    try:
        logger.log_user_action("text_analysis_started", st.session_state.session_id, {
            "text_length": len(text_input),
            "text_preview": text_input[:100] + "..." if len(text_input) > 100 else text_input
        })
        
        # OpenAI 서비스를 통한 분석 (함수 직접 호출)
        analysis_result = summarize_and_extract(text_input)
        
        # 결과를 Cosmos DB에 저장 (함수 직접 호출)
        meeting_id = str(uuid.uuid4())
        meeting_title = f"텍스트 분석 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        save_meeting(meeting_title, text_input, json.dumps(analysis_result))
        
        duration = time.time() - start_time
        logger.log_performance("text_analysis", duration, {
            "text_length": len(text_input),
            "analysis_length": len(str(analysis_result)) if analysis_result else 0
        })
        
        logger.log_business_event(
            "meeting_analysis_completed", 
            st.session_state.session_id, 
            meeting_id,
            f"Text analysis completed in {duration:.2f}s"
        )
        
        return analysis_result
        
    except Exception as e:
        duration = time.time() - start_time
        logger.log_error_with_context(
            "Failed to process text input",
            e,
            {
                "session_id": st.session_state.session_id,
                "text_length": len(text_input),
                "duration": duration
            }
        )
        return f"텍스트 분석 중 오류가 발생했습니다: {str(e)}"

def display_main_interface(services: Dict):
    """메인 사용자 인터페이스 표시 - 탭 기반 + 챗봇"""
    
    # 헤더
    st.markdown("""
    <div class="main-header">
        <h1>🤖 Meeting AI Assistant</h1>
        <p>AI 기반 회의 내용 분석 및 작업 할당 도구</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 메인 레이아웃: 왼쪽은 기존 기능, 오른쪽은 챗봇
    col_main, col_chat = st.columns([2, 1])
    
    with col_main:
        # 사이드바 - 기능 선택
        with st.sidebar:
            st.header("🔧 기능 선택")
            
            # 환경 정보 표시
            st.info(f"""
            **환경**: {config.environment.value}  
            **세션**: {st.session_state.session_id}  
            **시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}            """)
            
            feature = st.selectbox(
                "사용할 기능을 선택하세요",
                ["파일 업로드", "회의 기록 조회", "작업 항목 관리"],
                key="feature_selection"
            )
            
            # 로그 레벨 설정 (개발 환경에서만)
            if config.is_development():
                st.header("🐛 디버그 옵션")
                log_level = st.selectbox(
                    "로그 레벨",
                    ["INFO", "DEBUG", "WARNING", "ERROR"],
                    index=0                )
        
        # 메인 콘텐츠 영역 - 탭 기반 기능들
        if feature == "파일 업로드":
            display_file_upload_tab(services)
        elif feature == "회의 기록 조회":
            display_meeting_records_tab(services)
        elif feature == "작업 항목 관리":
            display_action_items_tab(services)
    
    with col_chat:
        # 오른쪽 챗봇 인터페이스
        st.header("💬 AI 챗봇")
        display_chat_interface(services)

def display_file_upload_tab(services: Dict):
    """파일 업로드 탭 표시"""
    
    st.markdown("""
    <div class="feature-card">
        <h3>📁 파일 업로드</h3>
        <p>회의 자료 파일을 업로드하면 자동으로 내용을 추출하고 분석합니다.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 허용 파일 형식 표시
    allowed_extensions = config.get("file_upload.allowed_extensions", [".pdf", ".docx", ".txt", ".wav", ".mp3"])
    max_size = config.get("file_upload.max_size_mb", 50)
    
    st.info(f"""
    **지원 파일 형식**: {', '.join(allowed_extensions)}  
    **최대 파일 크기**: {max_size}MB
    """)
    
    # 파일 업로드
    uploaded_file = st.file_uploader(
        "회의 자료 파일을 선택하세요",
        type=[ext.lstrip('.') for ext in allowed_extensions],
        key="file_upload"
    )
    
    if uploaded_file is not None:
        # 파일 정보 표시
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("파일명", uploaded_file.name)
        
        with col2:
            file_size_mb = uploaded_file.size / (1024 * 1024)
            st.metric("파일 크기", f"{file_size_mb:.2f} MB")
        
        with col3:
            st.metric("파일 형식", uploaded_file.type)
        
        # 업로드 처리 버튼
        if st.button("📤 파일 업로드 및 분석", type="primary", key="upload_file"):
            with st.spinner("파일을 업로드하고 분석하고 있습니다..."):
                result = process_uploaded_file(uploaded_file)
                
                if "오류" in result:
                    st.markdown(f"""
                    <div class="error-message">
                        <strong>❌ 업로드 실패</strong><br>
                        {result}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="success-message">
                        <strong>✅ 업로드 완료</strong><br>
                        {result}
                    </div>
                    """, unsafe_allow_html=True)

def display_meeting_records_tab(services: Dict):
    """회의 기록 조회 탭 표시"""
    
    st.markdown("""
    <div class="feature-card">
        <h3>📋 회의 기록 조회</h3>
        <p>이전에 분석된 회의 기록들을 조회하고 관리합니다.</p>
    </div>
    """, unsafe_allow_html=True)
    
    try:
        # 회의 기록 조회 (함수 직접 호출)
        meetings = get_meetings()
        
        if not meetings:
            st.info("아직 분석된 회의 기록이 없습니다. 텍스트 분석이나 파일 업로드를 통해 회의를 분석해보세요.")
        else:
            st.success(f"총 {len(meetings)}개의 회의 기록을 찾았습니다.")
            
            # 회의 목록 표시
            for i, meeting in enumerate(meetings):
                created_at = meeting.get('created_at', 'Unknown')
                title = meeting.get('title', f'회의 {i+1}')
                
                with st.expander(f"{title}: {created_at[:16]}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**회의 ID:**", meeting.get('id', 'N/A'))
                        st.write("**생성 시간:**", created_at)
                        st.write("**제목:**", title)
                    
                    with col2:
                        raw_text = meeting.get('raw_text', '')
                        st.write("**내용 미리보기:**")
                        st.write(raw_text[:200] + "..." if len(raw_text) > 200 else raw_text)
                    
                    # 요약 결과 표시
                    summary = meeting.get('summary')
                    if summary:
                        st.write("**요약 결과:**")
                        if isinstance(summary, str):
                            try:
                                summary_dict = json.loads(summary)
                                display_analysis_results(summary_dict)
                            except:
                                st.write(summary)
                        elif isinstance(summary, dict):
                            display_analysis_results(summary)
                        else:
                            st.write(str(summary))
                            
    except Exception as e:
        logger.log_error_with_context(
            "Failed to retrieve meeting records",
            e,
            {"session_id": st.session_state.session_id}
        )
        st.error(f"회의 기록을 불러오는 중 오류가 발생했습니다: {str(e)}")

def display_action_items_tab(services: Dict):
    """작업 항목 관리 탭 표시"""
    
    st.markdown("""
    <div class="feature-card">
        <h3>✅ 작업 항목 관리</h3>
        <p>회의에서 도출된 작업 항목들을 관리하고 추적합니다.</p>
    </div>
    """, unsafe_allow_html=True)
    
    try:
        # 먼저 모든 회의를 가져온 다음 각 회의의 액션 아이템을 조회
        meetings = get_meetings()
        all_action_items = []
        
        for meeting in meetings:
            meeting_id = meeting.get('id')
            if meeting_id:
                action_items = get_action_items(meeting_id)
                for item in action_items:
                    item['meeting_title'] = meeting.get('title', 'Unknown')
                    all_action_items.append(item)
        
        if not all_action_items:
            st.info("아직 등록된 작업 항목이 없습니다.")
        else:
            st.success(f"총 {len(all_action_items)}개의 작업 항목이 있습니다.")
            
            # 작업 항목 통계
            st.subheader("📊 작업 항목 현황")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("전체", len(all_action_items))
            
            with col2:
                st.metric("회의 수", len(meetings))
            
            with col3:
                st.metric("평균/회의", f"{len(all_action_items)/len(meetings):.1f}" if meetings else "0")
              # 작업 항목 목록
            for i, item in enumerate(all_action_items):
                with st.expander(f"📝 작업 항목 {i+1}: {item.get('description', 'No description')[:50]}..."):
                    st.write("**설명:**", item.get('description', 'N/A'))
                    st.write("**추천 담당자 ID:**", item.get('recommendedAssigneeId', 'N/A'))
                    st.write("**마감일:**", item.get('dueDate', 'N/A'))
                    st.write("**회의:**", item.get('meeting_title', 'N/A'))
                    st.write("**작업 ID:**", item.get('id', 'N/A'))
                            
    except Exception as e:
        logger.log_error_with_context(
            "Failed to display action items",
            e,
            {"session_id": st.session_state.session_id}
        )
        st.error(f"작업 항목을 불러오는 중 오류가 발생했습니다: {str(e)}")

def display_analysis_results(analysis: Dict):
    """분석 결과를 구조화하여 표시"""
    
    try:
        # 주요 내용 표시
        if 'summary' in analysis:
            st.subheader("📋 회의 요약")
            st.write(analysis['summary'])
        
        # 참석자 정보
        if 'participants' in analysis:
            st.subheader("👥 참석자")
            participants = analysis['participants']
            if isinstance(participants, list):
                for participant in participants:
                    st.write(f"- {participant}")
            else:
                st.write(participants)
        
        # 주요 결정사항
        if 'decisions' in analysis:
            st.subheader("✅ 주요 결정사항")
            decisions = analysis['decisions']
            if isinstance(decisions, list):
                for decision in decisions:
                    st.write(f"- {decision}")
            else:
                st.write(decisions)
        
        # 작업 항목
        if 'action_items' in analysis:
            st.subheader("📝 작업 항목")
            action_items = analysis['action_items']
            if isinstance(action_items, list):
                for item in action_items:
                    if isinstance(item, dict):
                        st.write(f"- **{item.get('task', 'N/A')}** (담당: {item.get('assignee', 'N/A')}, 마감: {item.get('due_date', 'N/A')})")
                    else:
                        st.write(f"- {item}")
            else:
                st.write(action_items)
        
        # 다음 회의 일정
        if 'next_meeting' in analysis:
            st.subheader("📅 다음 회의")
            st.write(analysis['next_meeting'])
            
    except Exception as e:
        logger.log_error_with_context(
            "Failed to display analysis results",
            e,
            {"analysis_keys": list(analysis.keys()) if isinstance(analysis, dict) else "not_dict"}
        )
        st.error("분석 결과 표시 중 오류가 발생했습니다.")

def display_chat_interface(services: Dict):
    """챗봇 인터페이스 표시 (오른쪽 컬럼용 간소화 버전)"""
    
    # 채팅 히스토리 초기화
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [
            {
                "role": "assistant", 
                "content": "안녕하세요! Meeting AI Assistant 챗봇입니다. 🤖\n\n어떻게 도와드릴까요?\n\n- 📝 회의 내용 텍스트 분석\n- 📁 파일 업로드 및 분석\n- 📋 회의 기록 조회\n- ✅ 작업 항목 관리"
            }
        ]
    
    # 채팅 메시지 표시 (높이 제한)
    with st.container():
        st.markdown("### 💬 AI 챗봇")
        
        # 메시지 컨테이너 (스크롤 가능)
        message_container = st.container()
        with message_container:
            for message in st.session_state.chat_messages[-5:]:  # 최근 5개 메시지만 표시
                with st.chat_message(message["role"]):
                    if message["role"] == "assistant" and "analysis_result" in message:
                        st.markdown(message["content"])
                        if isinstance(message["analysis_result"], dict):
                            with st.expander("분석 결과 보기"):
                                display_analysis_results(message["analysis_result"])
                    else:
                        st.markdown(message["content"])
    
    # 파일 업로드 (챗봇과 별도)
    with st.expander("📎 파일 업로드", expanded=False):
        allowed_extensions = config.get("file_upload.allowed_extensions", [".pdf", ".docx", ".txt", ".wav", ".mp3"])
        uploaded_file = st.file_uploader(
            "분석할 파일을 선택하세요",
            type=[ext.lstrip('.') for ext in allowed_extensions],
            key="chat_file_upload"
        )
        
        if uploaded_file is not None:
            if st.button("📤 파일 분석하기", key="chat_analyze_file"):
                with st.spinner(f"'{uploaded_file.name}' 파일을 처리하고 있습니다..."):
                    result = process_uploaded_file(uploaded_file)
                    
                    # 파일 처리 결과를 채팅에 추가
                    user_msg = f"파일을 업로드했습니다: {uploaded_file.name}"
                    st.session_state.chat_messages.append({"role": "user", "content": user_msg})
                    
                    if "오류" in result or "실패" in result:
                        response_msg = f"❌ 파일 처리 실패: {result}"
                    else:
                        response_msg = f"✅ 파일 처리 완료: {uploaded_file.name}"
                        
                    st.session_state.chat_messages.append({
                        "role": "assistant", 
                        "content": response_msg
                    })
                    st.rerun()
    
    # 챗봇 입력 처리 (파일 업로드 기능 제거)
    chat_prompt = st.chat_input(
        "회의 내용을 입력하거나 질문을 입력하세요",
        key="chat_input"
    )
    
    if chat_prompt:
        # 사용자 메시지 추가
        st.session_state.chat_messages.append({"role": "user", "content": chat_prompt})
        
        # 사용자 메시지 표시
        with st.chat_message("user"):
            st.markdown(chat_prompt)
        
        # AI 응답 생성
        with st.chat_message("assistant"):
            response_content = handle_text_input_response(chat_prompt, services)
            
            st.markdown(response_content["content"])
            
            # 분석 결과가 있으면 구조화하여 표시
            if "analysis_result" in response_content:
                with st.expander("분석 결과 보기"):
                    display_analysis_results(response_content["analysis_result"])
            
            # 응답을 세션에 저장
            st.session_state.chat_messages.append(response_content)

def handle_text_input_response(user_input: str, services: Dict) -> Dict:
    """텍스트 입력에 대한 AI 응답 처리"""
    start_time = time.time()
    
    try:
        # 간단한 키워드 기반 응답
        user_input_lower = user_input.lower()
        
        if any(keyword in user_input_lower for keyword in ['안녕', 'hello', '도움', 'help']):
            return {
                "role": "assistant",
                "content": "안녕하세요! 다음과 같은 기능을 제공합니다:\n\n📝 **텍스트 분석**: 회의 내용을 직접 입력하여 분석\n📁 **파일 업로드**: 문서나 음성 파일 업로드 및 분석\n📋 **회의 기록 조회**: 이전 분석 결과 조회\n✅ **작업 항목 관리**: 할당된 작업 확인 및 관리\n\n회의 내용을 입력하시면 바로 분석해드립니다!"
            }
        
        elif len(user_input) > 20:  # 텍스트 분석을 위한 최소 길이 (기존 50자에서 20자로 줄임)
            # 회의 내용으로 판단되는 경우 자동 분석
            try:
                analysis_result = process_text_input(user_input)
                
                if isinstance(analysis_result, dict):
                    return {
                        "role": "assistant",
                        "content": "회의 내용을 분석했습니다. 분석 결과를 확인해보세요! 📊",
                        "analysis_result": analysis_result
                    }
                else:
                    return {
                        "role": "assistant",
                        "content": f"📝 **분석 결과**\n\n{analysis_result}"
                    }
            except Exception as e:
                return {
                    "role": "assistant",
                    "content": f"분석 중 오류가 발생했습니다: {str(e)}\n\n다시 시도해보시거나 더 자세한 내용을 입력해 주세요."
                }
        
        elif any(keyword in user_input_lower for keyword in ['회의', '분석', 'meeting']):
            return {
                "role": "assistant",
                "content": "회의 내용 분석을 위해서는 더 자세한 내용을 입력해 주세요. (최소 20자 이상)\n\n예시:\n- 오늘 프로젝트 회의에서 논의된 내용들...\n- 마케팅 팀 회의 결과...\n- 개발팀 스프린트 리뷰 내용..."
            }
        
        elif any(keyword in user_input_lower for keyword in ['기록', '조회', '히스토리']):
            try:
                meetings = get_meetings()
                if meetings:
                    meeting_list = "\n".join([f"• {meeting.get('title', 'Unknown')}: {meeting.get('created_at', 'Unknown')[:16]}" for meeting in meetings[:5]])
                    return {
                        "role": "assistant",
                        "content": f"최근 회의 기록입니다:\n\n{meeting_list}\n\n더 자세한 정보는 '회의 기록 조회' 탭을 이용해주세요."
                    }
                else:
                    return {
                        "role": "assistant",
                        "content": "아직 저장된 회의 기록이 없습니다."
                    }
            except Exception as e:
                return {
                    "role": "assistant",
                    "content": f"회의 기록 조회 중 오류가 발생했습니다: {str(e)}"
                }
        
        else:
            # OpenAI 서비스를 통한 일반적인 질문 응답
            try:
                ai_response = ask_question(user_input)
                return {
                    "role": "assistant",
                    "content": ai_response
                }
            except Exception as e:
                return {
                    "role": "assistant",
                    "content": "죄송합니다. 현재 AI 서비스에 문제가 있습니다. 왼쪽의 기능 탭들을 이용해보시거나, 다시 시도해 주세요."
                }
        
        duration = time.time() - start_time
        logger.log_performance("chat_response", duration, {
            "user_input_length": len(user_input),
            "response_type": "text_analysis" if "분석" in user_input_lower else "general"
        })
        
    except Exception as e:
        duration = time.time() - start_time
        logger.log_error_with_context(
            "Failed to handle text input response",
            e,
            {
                "session_id": st.session_state.session_id,
                "user_input_length": len(user_input),
                "duration": duration
            }
        )
        return {
            "role": "assistant",
            "content": f"처리 중 오류가 발생했습니다: {str(e)}"
        }

def handle_file_upload_response(files_processed: List) -> Dict:
    """파일 업로드 결과에 대한 응답 처리"""
    
    success_files = []
    error_files = []
    
    for filename, result in files_processed:
        if "오류" in result or "실패" in result:
            error_files.append(f"❌ {filename}: {result}")
        else:
            success_files.append(f"✅ {filename}: 처리 완료")
    
    response_parts = []
    
    if success_files:
        response_parts.append("**성공적으로 처리된 파일:**")
        response_parts.extend(success_files)
    
    if error_files:
        response_parts.append("**처리 실패한 파일:**")
        response_parts.extend(error_files)
    
    if not success_files and not error_files:
        response_parts.append("파일 처리 결과를 확인할 수 없습니다.")
    
    return {
        "role": "assistant",
        "content": "\n".join(response_parts)
    }

def display_footer():
    """푸터 정보 표시"""
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**🔧 시스템 정보**")
        st.write(f"환경: {config.environment.value}")
        st.write(f"버전: {config.get('version', '1.0.0')}")
    
    with col2:
        st.markdown("**📊 세션 정보**")
        st.write(f"세션 ID: {st.session_state.session_id}")
        st.write(f"시작 시간: {datetime.now().strftime('%H:%M:%S')}")
    
    with col3:
        st.markdown("**🔗 유용한 링크**")
        if config.is_development():
            st.write("개발 환경에서 실행 중")
        else:
            st.write("프로덕션 환경에서 실행 중")

def main():
    """메인 애플리케이션 실행 함수"""
    
    try:
        # CSS 로드
        load_custom_css()
        
        # 서비스 초기화
        services = initialize_services()
        
        if services is None:
            st.error("Azure 서비스 초기화에 실패했습니다. 환경 설정을 확인해주세요.")
            st.info("""
            **확인 사항:**
            1. .env 파일에 모든 Azure 서비스 키가 설정되어 있는지 확인
            2. Azure 서비스들이 활성 상태인지 확인
            3. 네트워크 연결 상태 확인
            """)
            
            # 개발 환경에서는 더 자세한 정보 표시
            if config.is_development():
                st.write("**환경 변수 상태:**")
                credentials = config.get_azure_credentials()
                for key, value in credentials.items():
                    status = "✅ 설정됨" if value else "❌ 미설정"
                    st.write(f"- {key}: {status}")
            
            return
        
        # 메인 인터페이스 표시
        display_main_interface(services)
        
        # 푸터 표시
        display_footer()
        
    except Exception as e:
        logger.log_error_with_context(
            "Critical application error",
            e,
            {"session_id": st.session_state.get('session_id', 'unknown')}
        )
        
        st.error("애플리케이션 실행 중 치명적인 오류가 발생했습니다.")
        st.exception(e)
        
        if config.is_development():
            st.write("**디버그 정보:**")
            st.write(f"환경: {config.environment.value}")
            st.write(f"오류: {str(e)}")

if __name__ == "__main__":
    main()
