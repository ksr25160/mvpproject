# 서비스 함수들을 쉽게 사용하기 위한 래퍼
"""
Meeting AI Assistant - 서비스 래퍼
함수 기반 서비스들을 쉽게 사용할 수 있도록 도와주는 래퍼 모듈
"""

# OpenAI 서비스 함수들
from services.openai_service import (
    transcribe_audio,
    summarize_and_extract,
    apply_json_modification,
    ask_question,
    ask_question_with_search
)

# Blob 서비스 함수들
from services.blob_service import upload_to_blob

# Search 서비스 함수들  
from services.search_service import index_document, search_documents

# Cosmos DB 함수들
from db.cosmos_db import (
    init_cosmos,
    save_meeting,
    save_action_items,
    get_meetings,
    get_meeting,
    get_action_items,
    update_action_item,
    approve_action_item,
    update_action_item_status,
    save_approval_history,
    save_audit_log,
    apply_json_modification as cosmos_apply_modification
)

class ServiceManager:
    """서비스 매니저 - 모든 함수를 쉽게 접근할 수 있게 해주는 클래스"""
    
    def __init__(self):
        # Cosmos DB 초기화
        try:
            init_cosmos()
            self.cosmos_initialized = True
        except Exception as e:
            print(f"Warning: Cosmos DB initialization failed: {e}")
            self.cosmos_initialized = False
    
    # OpenAI 서비스
    def transcribe_audio(self, file_path: str) -> str:
        return transcribe_audio(file_path)
    
    def summarize_and_extract(self, text: str) -> dict:
        return summarize_and_extract(text)
    
    def apply_json_modification(self, original_json_str: str, mod_request: str) -> dict:
        return apply_json_modification(original_json_str, mod_request)
    
    def ask_question(self, all_text: str, question: str) -> str:
        return ask_question(all_text, question)
    
    def ask_question_with_search(self, query: str) -> str:
        return ask_question_with_search(query)
    
    # Blob 서비스
    def upload_to_blob(self, file_path: str, blob_name: str) -> str:
        return upload_to_blob(file_path, blob_name)
    
    # Search 서비스
    def index_document(self, doc_id: str, content: str, metadata: dict) -> None:
        return index_document(doc_id, content, metadata)
    
    def search_documents(self, query: str, top: int = 3) -> list:
        return search_documents(query, top)
    
    # Cosmos DB 서비스
    def save_meeting(self, meeting_title: str, raw_text: str, summary_json: str) -> str:
        return save_meeting(meeting_title, raw_text, summary_json)
    
    def get_meetings(self, top: int = 100) -> list:
        return get_meetings(top)
    
    def get_meeting(self, meeting_id: str) -> dict:
        return get_meeting(meeting_id)
    
    def get_action_items(self, meeting_id: str) -> list:
        return get_action_items(meeting_id)
    
    def update_action_item_status(self, item_id: str, meeting_id: str, status: str) -> None:
        return update_action_item_status(item_id, meeting_id, status)
    
    def approve_action_item(self, item_id: str, meeting_id: str, final_assignee_id: str, reviewer_name: str = None) -> None:
        return approve_action_item(item_id, meeting_id, final_assignee_id, reviewer_name)

# 전역 서비스 매니저 인스턴스
service_manager = ServiceManager()
