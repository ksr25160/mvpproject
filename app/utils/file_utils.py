"""
Meeting AI Assistant - 파일 처리 유틸리티
"""
import streamlit as st
import tempfile
import os

def process_uploaded_file_from_chat(uploaded_file, service_manager):
    """파일 업로드 처리"""
    try:
        # 처리 상태 설정
        st.session_state.processing = True
        
        # 처리 시작 메시지 추가
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": f"🔄 {uploaded_file.name} 파일을 처리하고 있습니다..."
        })
        
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{uploaded_file.name}") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            temp_file_path = tmp_file.name
        
        try:
            # 파일 타입에 따른 처리
            file_extension = uploaded_file.name.lower().split('.')[-1]
            
            if file_extension in ['mp3', 'wav', 'mp4', 'm4a']:
                response = _process_audio_file(uploaded_file, temp_file_path, service_manager)
            elif file_extension in ['pdf', 'txt', 'docx']:
                response = _process_text_file(uploaded_file, temp_file_path, file_extension, service_manager)
            else:
                response = f"❌ 지원하지 않는 파일 형식입니다: {file_extension}"
            
        finally:
            # 임시 파일 삭제
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        
        # 처리 중 메시지를 결과 메시지로 업데이트
        if st.session_state.chat_messages and st.session_state.chat_messages[-1]["content"].startswith("🔄"):
            st.session_state.chat_messages[-1]["content"] = response
        else:
            st.session_state.chat_messages.append({
                "role": "assistant",
                "content": response
            })
        
    except Exception as e:
        error_message = f"❌ 파일 처리 중 오류가 발생했습니다: {str(e)}"
        
        # 처리 중 메시지를 오류 메시지로 업데이트
        if st.session_state.chat_messages and st.session_state.chat_messages[-1]["content"].startswith("🔄"):
            st.session_state.chat_messages[-1]["content"] = error_message
        else:
            st.session_state.chat_messages.append({
                "role": "assistant",
                "content": error_message
            })
    finally:
        # 처리 상태 해제
        st.session_state.processing = False
        # 파일 처리 완료 후 UI 업데이트
        st.rerun()

def _process_audio_file(uploaded_file, temp_file_path, service_manager):
    """음성 파일 처리"""
    try:
        transcribed_text = service_manager.transcribe_audio(temp_file_path)
        
        if transcribed_text:
            # AI 분석
            analysis_result = service_manager.summarize_and_extract(transcribed_text)
            
            # 결과를 Cosmos DB에 저장
            meeting_id = service_manager.save_meeting(
                meeting_title=analysis_result.get("meetingTitle", uploaded_file.name),
                raw_text=transcribed_text,
                summary_json=analysis_result
            )
            
            # 응답 메시지 생성
            response = f"""✅ **음성 파일 분석 완료**

**파일명:** {uploaded_file.name}
**회의 제목:** {analysis_result.get('meetingTitle', 'N/A')}
**참석자:** {', '.join(analysis_result.get('participants', ['N/A']))}

**요약:**
{analysis_result.get('summary', 'N/A')}

**액션 아이템:** {len(analysis_result.get('actionItems', []))}개"""
            
            for i, item in enumerate(analysis_result.get('actionItems', [])[:3], 1):
                response += f"\n{i}. {item.get('description', 'N/A')} (담당: {item.get('assignee', 'N/A')})"
            
            if len(analysis_result.get('actionItems', [])) > 3:
                response += f"\n... 외 {len(analysis_result.get('actionItems', [])) - 3}개"
            
        else:
            response = f"❌ 음성 파일 {uploaded_file.name}의 전사에 실패했습니다."
        
        return response
        
    except Exception as e:
        return f"❌ 음성 파일 처리 중 오류가 발생했습니다: {str(e)}"

def _process_text_file(uploaded_file, temp_file_path, file_extension, service_manager):
    """텍스트 파일 처리"""
    try:
        if file_extension == 'txt':
            with open(temp_file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
        else:
            file_content = f"텍스트 파일 {uploaded_file.name}이 업로드되었습니다. (PDF/DOCX 파싱은 향후 구현 예정)"
        
        if file_content:
            # AI 분석
            analysis_result = service_manager.summarize_and_extract(file_content)
            
            # 결과를 Cosmos DB에 저장
            meeting_id = service_manager.save_meeting(
                meeting_title=analysis_result.get("meetingTitle", uploaded_file.name),
                raw_text=file_content,
                summary_json=analysis_result
            )
            
            response = f"""✅ **문서 분석 완료**

**파일명:** {uploaded_file.name}
**회의 제목:** {analysis_result.get('meetingTitle', 'N/A')}

**요약:**
{analysis_result.get('summary', 'N/A')}

**액션 아이템:** {len(analysis_result.get('actionItems', []))}개"""
        else:
            response = f"❌ 파일 {uploaded_file.name}을 읽을 수 없습니다."
        
        return response
        
    except Exception as e:
        return f"❌ 파일 처리 중 오류가 발생했습니다: {str(e)}"
