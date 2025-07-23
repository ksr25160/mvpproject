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
        
        # 간단한 키워드 기반 응답 (실제 AI 서비스 연동 전 단계)
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
            response += f"\n{i}. {meeting.get('title', 'N/A')} ({meeting.get('date', 'N/A')})"
        
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
        # AI Search 기능 사용 (향후 구현)
        from services.search_service import search_documents
        search_results = search_documents(user_input, top=3)
        if search_results:
            response = f"""
🔍 **검색 결과**

"{user_input}"에 대한 검색 결과:

"""
            for i, result in enumerate(search_results, 1):
                response += f"{i}. {result.get('title', 'N/A')}\n"
                response += f"   {result.get('content', 'N/A')[:100]}...\n\n"
        else:
            response = "🔍 검색 결과가 없습니다. 다른 키워드로 시도해보세요."
    except:
        response = "🔍 검색 기능은 현재 준비 중입니다."
    
    return response

def _handle_modification_query(user_input, service_manager):
    """자연어 수정 기능 처리"""
    try:
        # 회의 목록 조회
        meetings = service_manager.get_meetings()
        
        # 스마트한 회의 매칭
        target_meeting = None
        
        # 1. 정확한 제목이나 ID 매칭
        for meeting in meetings:
            meeting_title = meeting.get('title', '').lower()
            meeting_id = meeting.get('id', '').lower()
            if meeting_title in user_input.lower() or meeting_id in user_input.lower():
                target_meeting = meeting
                break
        
        # 2. 부분 매칭 (제목의 일부가 포함된 경우)
        if not target_meeting:
            for meeting in meetings:
                meeting_title = meeting.get('title', '').lower()
                # 제목을 단어별로 분리하여 매칭
                title_words = meeting_title.split()
                if any(word in user_input.lower() for word in title_words if len(word) > 2):
                    target_meeting = meeting
                    break
        
        # 3. 인덱스 기반 선택 ("첫 번째 회의", "두 번째 회의" 등)
        if not target_meeting:
            numbers = {'첫': 0, '첫번째': 0, '두': 1, '두번째': 1, '세': 2, '세번째': 2, 
                      '네': 3, '네번째': 3, '다섯': 4, '다섯번째': 4}
            
            for key, index in numbers.items():
                if key in user_input and index < len(meetings):
                    target_meeting = meetings[index]
                    break
            
            # 숫자로 된 인덱스도 확인
            number_match = re.search(r'(\d+)번째', user_input)
            if number_match:
                index = int(number_match.group(1)) - 1
                if 0 <= index < len(meetings):
                    target_meeting = meetings[index]
        
        if target_meeting:
            # 회의가 특정된 경우 수정 수행
            meeting_id = target_meeting.get('id')
            original_summary = target_meeting.get('summary_json', {})
            
            # OpenAI로 자연어 수정 요청
            print(f"🔧 자연어 수정 요청: {user_input}")
            modified_result = service_manager.apply_json_modification(
                json.dumps(original_summary) if isinstance(original_summary, dict) else str(original_summary),
                user_input
            )
            
            # 수정된 내용으로 회의록 업데이트
            if isinstance(modified_result, dict):
                service_manager.update_meeting(meeting_id, {
                    'summary_json': modified_result,
                    'summary': modified_result.get('summary', original_summary.get('summary', '')),
                    'title': modified_result.get('meetingTitle', target_meeting.get('title', ''))
                })
                print(f"✅ 회의 {meeting_id} 업데이트 완료")
            
            response = f"""
✅ **자연어 수정 완료**

**회의:** {target_meeting.get('title', 'N/A')}
**수정 요청:** {user_input}

**수정된 내용:**
{json.dumps(modified_result, ensure_ascii=False, indent=2) if isinstance(modified_result, dict) else str(modified_result)}

💡 수정사항이 적용되었습니다. Meeting Records에서 확인하세요.
"""
        else:
            # 회의가 특정되지 않은 경우 - 회의 목록 제공                    
            response = f"""
🔍 **수정할 회의를 지정해주세요**

현재 저장된 회의록:
"""
            for i, meeting in enumerate(meetings[:5], 1):
                response += f"\n{i}. {meeting.get('title', 'N/A')} (ID: {meeting.get('id', 'N/A')})"
            
            response += f"""

📝 **사용법 예시:**
• "첫 번째 회의의 제목을 '주간 회의'로 수정해줘"
• "프로젝트 회의의 요약을 더 자세하게 해줘"  
• "meeting_123의 참석자에 김철수를 추가해줘"
• "마지막 회의의 액션 아이템을 수정해줘"

💡 회의 제목의 일부만 언급해도 찾을 수 있어요!
"""
            
    except Exception as e:
        response = f"❌ 자연어 수정 중 오류가 발생했습니다: {str(e)}"
    
    return response

def _handle_staff_query(user_input, service_manager):
    """인사정보 관련 질문 처리"""
    try:
        if any(keyword in user_input.lower() for keyword in ['추천', 'recommend', '누가']):
            # 담당자 추천
            if any(keyword in user_input.lower() for keyword in ['개발', 'development', 'code', 'programming']):
                recommended = service_manager.recommend_assignee_for_task(user_input)
                if recommended:
                    response = f"""
🎯 **담당자 추천**

**추천된 담당자:** {recommended.get('name', 'N/A')}
**부서:** {recommended.get('department', 'N/A')}
**직책:** {recommended.get('position', 'N/A')}
**이메일:** {recommended.get('email', 'N/A')}
**관련 스킬:** {', '.join(recommended.get('skills', []))}

💡 이 담당자가 해당 작업에 적합할 것 같습니다!
"""
                else:
                    response = "❌ 적절한 담당자를 찾을 수 없습니다."
            else:
                response = "🤔 어떤 작업에 대한 담당자를 추천받고 싶으신가요? (예: '웹 개발 담당자 추천해줘')"
        
        elif any(keyword in user_input.lower() for keyword in ['목록', 'list', '전체', '모든', '모두']):
            # 직원 목록 조회
            staff_list = service_manager.get_all_staff()
            if staff_list:
                response = f"""
👥 **직원 목록** ({len(staff_list)}명)

"""
                for i, staff in enumerate(staff_list[:10], 1):  # 최대 10명까지만 표시
                    response += f"{i}. **{staff.get('name', 'N/A')}** ({staff.get('department', 'N/A')})\n"
                    response += f"   └ {staff.get('position', 'N/A')} | {staff.get('email', 'N/A')}\n\n"
                
                if len(staff_list) > 10:
                    response += f"... 외 {len(staff_list) - 10}명\n\n"
                
                response += "📋 Staff Management 페이지에서 상세 정보를 확인하고 관리할 수 있습니다."
            else:
                response = "👥 등록된 직원이 없습니다. Staff Management에서 직원을 추가해보세요!"
        
        elif any(keyword in user_input.lower() for keyword in ['찾기', '검색', '누구']):
            # 특정 직원 검색
            search_term = user_input.lower()
            staff_list = service_manager.get_all_staff()
            
            found_staff = []
            for staff in staff_list:
                if (search_term in staff.get('name', '').lower() or 
                    search_term in staff.get('department', '').lower() or
                    search_term in staff.get('position', '').lower()):
                    found_staff.append(staff)
            
            if found_staff:
                response = f"""
🔍 **검색 결과** ({len(found_staff)}명)

"""
                for staff in found_staff[:5]:  # 최대 5명까지만 표시
                    response += f"👤 **{staff.get('name', 'N/A')}**\n"
                    response += f"   🏢 {staff.get('department', 'N/A')} | {staff.get('position', 'N/A')}\n"
                    response += f"   📧 {staff.get('email', 'N/A')}\n"
                    skills = staff.get('skills', [])
                    if skills:
                        response += f"   💡 {', '.join(skills[:3])}\n"
                    response += "\n"
            else:
                response = "🔍 검색 조건에 맞는 직원을 찾을 수 없습니다."
        
        else:
            # 일반적인 인사정보 도움말
            staff_count = len(service_manager.get_all_staff())
            response = f"""
👥 **인사정보 관리**

현재 등록된 직원: **{staff_count}명**

**사용 가능한 명령어:**
• "직원 목록 보여줘" - 전체 직원 목록 조회
• "개발팀 직원 찾아줘" - 특정 부서 직원 검색  
• "김민수 찾아줘" - 특정 직원 정보 조회
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
- "프로젝트 관련 회의 찾아줘"
- "개발 담당자 추천해줘"

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
        # 현재 세션의 전체 대화를 저장
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
