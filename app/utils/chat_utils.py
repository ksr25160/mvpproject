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
        print(f"💬 사용자 질문: {user_input[:50]}...")
        
        # 사용자 메시지 추가
        st.session_state.chat_messages.append({
            "role": "user",
            "content": user_input
        })
        
        # 처리 상태 설정
        st.session_state.processing = True
        st.rerun()
        
        # 간단한 키워드 기반 응답
        response = ""
        if any(keyword in user_input.lower() for keyword in ['회의', '미팅', '회의록']):
            response = _handle_meeting_query(user_input, service_manager)
        elif any(keyword in user_input.lower() for keyword in ['작업', '업무', '할일', 'todo', 'task']):
            response = _handle_task_query(user_input, service_manager)
        elif any(keyword in user_input.lower() for keyword in ['검색', 'search', '찾기']):
            response = _handle_search_query(user_input)
        elif any(keyword in user_input.lower() for keyword in ['수정', '변경', '업데이트', 'modify', 'update', 'change']):
            response = _handle_modification_query(user_input, service_manager)
        elif any(keyword in user_input.lower() for keyword in ['직원', '인사', '사람', 'staff', '담당자', '추천']):
            response = _handle_staff_query(user_input, service_manager)
        else:
            # 일반적인 질문은 검색 기반 OpenAI로 처리
            try:
                print(f"🤖 OpenAI 서비스 호출 시작: {user_input}")
                response = service_manager.ask_question_with_search(user_input)
                print(f"✅ OpenAI 응답 완료")
                
                # 검색 결과가 없는 경우 기본 도움말 제공
                if "관련 회의록을 찾을 수 없습니다" in response:
                    response = _handle_general_help()
                    
            except Exception as e:
                print(f"❌ OpenAI 서비스 오류: {str(e)}")
                response = _handle_general_help()
        
        # AI 응답 추가
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": response
        })
        
        # 채팅 히스토리에 추가
        add_to_chat_history(user_input, response, service_manager)
        
        print(f"✅ 질문 처리 완료")
        
    except Exception as e:
        error_response = f"❌ 질문 처리 중 오류가 발생했습니다: {str(e)}"
        print(f"❌ 질문 처리 오류: {str(e)}")
        
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": error_response
        })
    
    finally:
        # 처리 상태 해제
        st.session_state.processing = False
        st.rerun()

def _handle_meeting_query(user_input, service_manager):
    """회의 관련 질문 처리"""
    meetings = service_manager.get_meetings()
    if meetings:
        response = f"""
📝 **회의록 관련 정보**

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
        meetings = service_manager.get_meetings()
        all_action_items = []
        for meeting in meetings:
            meeting_id = meeting.get('id')
            if meeting_id:
                action_items = service_manager.get_action_items(meeting_id)
                all_action_items.extend(action_items)
        
        if all_action_items:
            completed = len([item for item in all_action_items if item.get('status') == '완료'])
            pending = len(all_action_items) - completed
            
            response = f"""
✅ **작업 현황**

전체 작업: {len(all_action_items)}개
완료: {completed}개
대기중: {pending}개

최근 작업:
"""
            for i, task in enumerate(all_action_items[:3], 1):
                status = "✅" if task.get('status') == '완료' else "⏳"
                response += f"\n{i}. {status} {task.get('description', 'N/A')}"
            
            response += "\n\n📋 Task Management 페이지에서 자세한 관리가 가능합니다."
        else:
            response = "✅ 등록된 작업이 없습니다. 회의를 분석하면 자동으로 액션 아이템이 생성됩니다!"
            
    except Exception as e:
        response = f"❌ 작업 정보를 가져오는 중 오류가 발생했습니다: {str(e)}"
    
    return response

def _handle_search_query(user_input):
    """검색 관련 질문 처리"""
    try:
        # AI Search 기능 사용
        from services.search_service import search_documents
        search_results = search_documents(user_input, top=3)
        if search_results:
            response = f"""
🔍 **검색 결과**

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
        meeting_id = target_meeting.get('id')
        original_summary = target_meeting.get('summary_json', {})
        
        # OpenAI로 자연어 수정 요청
        print(f"🔧 자연어 수정 요청: {user_input}")
        modified_result = service_manager.apply_json_modification(
            json.dumps(original_summary) if isinstance(original_summary, dict) else str(original_summary),
            user_input
        )
        
        response = f"""
✅ **자연어 수정 완료**

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
        
        if any(keyword in user_input.lower() for keyword in ['목록', 'list', '전체', '모든', '모두']):
            if staff_list:
                response = f"""
👥 **직원 목록** ({staff_count}명)

"""
                for i, staff in enumerate(staff_list[:5], 1):
                    response += f"{i}. **{staff.get('name', 'N/A')}** ({staff.get('department', 'N/A')})\n"
                    response += f"   └ {staff.get('position', 'N/A')} | {staff.get('email', 'N/A')}\n\n"
                
                if len(staff_list) > 5:
                    response += f"... 외 {len(staff_list) - 5}명\n\n"
                
                response += "📋 Staff Management 페이지에서 상세 정보를 확인하고 관리할 수 있습니다."
            else:
                response = "👥 등록된 직원이 없습니다. Staff Management에서 직원을 추가해보세요!"
        else:
            response = f"""
👥 **인사정보 관리**

현재 등록된 직원: **{staff_count}명**

**사용 가능한 명령어:**
• "직원 목록 보여줘" - 전체 직원 목록 조회
• "개발팀 직원 찾아줘" - 특정 부서 직원 검색  
• "개발 담당자 추천해줘" - 작업에 적합한 담당자 추천

📋 Staff Management 페이지에서 직원 정보를 추가/수정/삭제할 수 있습니다.
"""
            
    except Exception as e:
        response = f"❌ 인사정보 조회 중 오류가 발생했습니다: {str(e)}"
    
    return response

def _handle_general_help():
    """일반적인 도움말 응답"""
    return f"""
🤖 **Meeting AI Assistant입니다**

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
    """채팅 히스토리에 대화 추가 및 DB 저장"""
    chat_entry = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M'),
        "preview": user_message,
        "messages": [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": ai_response}
        ]
    }
    
    # 세션 상태에 추가
    st.session_state.chat_history.append(chat_entry)
    
    # 히스토리가 너무 길어지면 오래된 것 삭제
    if len(st.session_state.chat_history) > 50:
        st.session_state.chat_history = st.session_state.chat_history[-50:]
    
    # DB에 저장
    try:
        session_id = st.session_state.get('session_id', 'unknown')
        all_messages = st.session_state.get('chat_messages', [])
        
        # 대화가 있을 때만 저장 (최소 2개 이상의 메시지)
        if len(all_messages) >= 2:
            summary = user_message[:50] + "..." if len(user_message) > 50 else user_message
            chat_id = service_manager.save_chat_history(session_id, all_messages, summary)
            if chat_id:
                print(f"✅ 채팅 히스토리 DB 저장 완료: {chat_id}")
    except Exception as e:
        print(f"❌ 채팅 히스토리 DB 저장 오류: {str(e)}")

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
    
    print(f"✅ 새로운 채팅 세션 초기화: {st.session_state.session_id}")

def clear_current_chat():
    """현재 채팅 내용만 클리어 (세션 ID는 유지)"""
    st.session_state.chat_messages = []
    st.session_state.chat_history = []
    st.session_state.processing = False
    print("✅ 현재 채팅 내용 클리어 완료")

def load_chat_history_from_db(chat_id, service_manager):
    """DB에서 특정 채팅 히스토리 로드"""
    try:
        chat_data = service_manager.get_chat_history_by_id(chat_id)
        if chat_data and 'messages' in chat_data:
            # 채팅 메시지 복원
            st.session_state.chat_messages = chat_data['messages']
            
            # UI용 히스토리도 업데이트
            st.session_state.chat_history = []
            for i in range(0, len(chat_data['messages']), 2):
                if i + 1 < len(chat_data['messages']):
                    user_msg = chat_data['messages'][i]
                    ai_msg = chat_data['messages'][i + 1]
                    
                    entry = {
                        "timestamp": chat_data.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M')),
                        "preview": user_msg.get('content', '')[:50],
                        "messages": [user_msg, ai_msg]
                    }
                    st.session_state.chat_history.append(entry)
            
            print(f"✅ 채팅 히스토리 로드 완료: {chat_id}")
            return True
    except Exception as e:
        print(f"❌ 채팅 히스토리 로드 오류: {str(e)}")
    return False
