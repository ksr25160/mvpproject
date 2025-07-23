"""
Meeting AI Assistant - Chat 페이지 렌더링
"""
import streamlit as st
import tempfile
import os
import json
from datetime import datetime

def render_chatbot(service_manager, fullwidth=False):
    """챗봇 패널 렌더링"""
    
    # 채팅 컨테이너
    chat_container = st.container()
    
    with chat_container:
        # 헤더
        st.markdown("### 🤖 AI Assistant")
        
        # 메시지가 없을 때 환영 메시지
        if not st.session_state.chat_messages:
            with st.chat_message("assistant"):
                st.markdown("""
                👋 **안녕하세요! Meeting AI Assistant입니다.**
                
                📁 **파일 업로드:** 음성/문서 파일을 드래그하거나 📎 버튼을 클릭하세요  
                💬 **질문하기:** 회의, 작업, 검색에 대해 무엇이든 물어보세요  
                🔍 **기능:** 회의 분석, 작업 관리, 문서 검색 등을 지원합니다
                """)
        
        # 기존 메시지들 표시 (우측 패널에서는 최근 5개만 표시)
        display_messages = st.session_state.chat_messages
        if not fullwidth:
            # 우측 패널에서는 최근 5개 메시지만 표시하여 스크롤 최소화
            display_messages = st.session_state.chat_messages[-5:] if len(st.session_state.chat_messages) > 5 else st.session_state.chat_messages
            
            if len(st.session_state.chat_messages) > 5:
                st.caption(f"이전 메시지 {len(st.session_state.chat_messages) - 5}개가 더 있습니다. Chat 탭에서 전체 대화를 확인하세요.")
        
        for message in display_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                # 파일이 첨부된 경우 표시
                if message.get("files"):
                    st.caption("📎 첨부 파일:")
                    for file_info in message["files"]:
                        st.caption(f"- {file_info['name']} ({file_info['size']} bytes)")
        
        # 처리 중 표시
        if st.session_state.processing:
            with st.chat_message("assistant"):
                st.info("🤖 AI가 응답을 생성하고 있습니다...")

    # 채팅 입력 (파일 업로드 통합)
    prompt = st.chat_input(
        "메시지를 입력하거나 파일을 첨부하세요...",
        accept_file="multiple",
        file_type=["mp3", "wav", "mp4", "m4a", "pdf", "txt", "docx"]    )
    if prompt:
        # 텍스트 입력 처리
        if prompt.text:
            import sys
            from pathlib import Path
            # utils 모듈을 찾기 위해 상위 디렉토리를 Python 경로에 추가
            sys.path.append(str(Path(__file__).parent.parent))
            from utils.chat_utils import process_chat_message
            process_chat_message(prompt.text, service_manager)
        
        # 파일 업로드 처리
        if prompt.files:
            import sys
            from pathlib import Path
            # utils 모듈을 찾기 위해 상위 디렉토리를 Python 경로에 추가
            sys.path.append(str(Path(__file__).parent.parent))
            from utils.file_utils import process_uploaded_file_from_chat
            
            # 파일 정보 표시
            file_info_msg = f"📎 {len(prompt.files)}개 파일 첨부: "
            file_names = [f.name for f in prompt.files]
            file_info_msg += ", ".join(file_names)
            
            st.session_state.chat_messages.append({
                "role": "user",
                "content": file_info_msg
            })
            
            # 각 파일 처리
            for uploaded_file in prompt.files:
                process_uploaded_file_from_chat(uploaded_file, service_manager)
