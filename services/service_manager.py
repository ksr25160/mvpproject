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
    ask_question_with_search,
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
    apply_json_modification as cosmos_apply_modification,
    init_staff_data,
    get_all_staff,
    get_staff_by_id,
    update_staff,
    add_staff,
    delete_staff,
    recommend_assignee_for_task,
    save_chat_history,
    get_chat_histories,
    get_chat_history_by_id,
    delete_chat_history,
    update_chat_history_summary,
    add_new_action_item,
    find_staff_by_name,
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
    def index_document(
        self, doc_id: str, content: str, metadata: dict, blob_path: str = None
    ) -> None:
        return index_document(doc_id, content, metadata, blob_path)

    def search_documents(self, query: str, top: int = 3) -> list:
        return search_documents(query, top)

    # Cosmos DB 서비스
    def save_meeting(self, meeting_title: str, raw_text: str, summary_json: str) -> str:
        return save_meeting(meeting_title, raw_text, summary_json)

    def save_action_items(self, meeting_id: str, action_items: list) -> None:
        return save_action_items(meeting_id, action_items)

    def get_meetings(self, top: int = 100) -> list:
        return get_meetings(top)

    def get_meeting(self, meeting_id: str) -> dict:
        return get_meeting(meeting_id)

    def get_action_items(self, meeting_id: str) -> list:
        return get_action_items(meeting_id)

    def get_all_action_items(self) -> list:
        from db.cosmos_db import get_all_action_items

        return get_all_action_items()

    def update_action_item_status(
        self, item_id: str, meeting_id: str, status: str
    ) -> None:
        return update_action_item_status(item_id, meeting_id, status)

    def approve_action_item(
        self,
        item_id: str,
        meeting_id: str,
        final_assignee_id: str,
        reviewer_name: str = None,
    ) -> None:
        return approve_action_item(
            item_id, meeting_id, final_assignee_id, reviewer_name
        )

    def update_meeting(self, meeting_id: str, updates: dict) -> dict:
        from db.cosmos_db import update_meeting

        return update_meeting(meeting_id, updates)

    # 인사정보 관리 서비스
    def init_staff_data(self) -> None:
        """더미 인사정보 초기화"""
        return init_staff_data()

    def get_all_staff(self) -> list:
        """모든 인사정보 조회"""
        return get_all_staff()

    def get_staff_by_id(self, staff_id: str) -> dict:
        """ID로 특정 인사정보 조회"""
        return get_staff_by_id(staff_id)

    def update_staff(self, staff_id: str, updates: dict) -> bool:
        """인사정보 업데이트"""
        return update_staff(staff_id, updates)

    def add_staff(self, staff_data: dict) -> str:
        """새로운 인사정보 추가"""
        return add_staff(staff_data)

    def delete_staff(self, staff_id: str) -> bool:
        """인사정보 삭제"""
        return delete_staff(staff_id)

    def recommend_assignee_for_task(
        self, task_description: str, task_skills=None
    ) -> dict:
        """작업 내용에 따른 담당자 추천"""
        return recommend_assignee_for_task(task_description, task_skills)

    # 채팅 히스토리 관리 서비스
    def save_chat_history(
        self, session_id: str, messages: list, summary: str = None
    ) -> str:
        """채팅 히스토리 저장"""
        from db.cosmos_db import save_chat_history

        return save_chat_history(session_id, messages, summary)

    def get_chat_histories(self, session_id: str = None, limit: int = 20) -> list:
        """채팅 히스토리 목록 조회"""
        from db.cosmos_db import get_chat_histories

        return get_chat_histories(session_id, limit)

    def get_chat_history_by_id(self, chat_id: str) -> dict:
        """특정 채팅 히스토리 조회"""
        from db.cosmos_db import get_chat_history_by_id

        return get_chat_history_by_id(chat_id)

    def delete_chat_history(self, chat_id: str) -> bool:
        """채팅 히스토리 삭제"""
        from db.cosmos_db import delete_chat_history

        return delete_chat_history(chat_id)

    def update_chat_history_summary(self, chat_id: str, new_summary: str) -> bool:
        """채팅 히스토리 요약 업데이트"""
        from db.cosmos_db import update_chat_history_summary

        return update_chat_history_summary(chat_id, new_summary)

    # 새로운 액션 아이템 관리 기능
    def add_new_action_item(
        self,
        task_description: str,
        assignee_name: str = None,
        due_date: str = None,
        meeting_id: str = None,
    ) -> str:
        """새로운 액션 아이템 추가"""
        return add_new_action_item(
            task_description, assignee_name, due_date, meeting_id
        )

    def find_staff_by_name(self, name: str) -> dict:
        """이름으로 직원 찾기"""
        return find_staff_by_name(name)

    def update_action_item_assignee(
        self, item_id: str, meeting_id: str, assignee_name: str
    ) -> bool:
        """액션 아이템의 담당자 업데이트"""
        try:
            from db.cosmos_db import update_action_item_assignee

            return update_action_item_assignee(item_id, meeting_id, assignee_name)
        except Exception as e:
            print(f"❌ 담당자 업데이트 실패: {e}")
            return False

    # RAG 기반 담당자 추천
    def index_staff_data_for_search(self) -> bool:
        """직원 정보를 직원 전용 AI Search 인덱스에 업데이트"""
        try:
            from services.search_service import index_staff_data_to_search

            # Cosmos DB에서 모든 직원 정보 조회
            staff_list = self.get_all_staff()
            if not staff_list:
                print("⚠️ 인덱싱할 직원 정보가 없습니다")
                return False

            # 직원 전용 인덱스에 업데이트 (기존 데이터 덮어쓰기)
            result = index_staff_data_to_search(staff_list)

            if result:
                print(f"✅ 직원 정보 인덱싱 완료: {len(staff_list)}명")
                return True
            else:
                print("❌ 직원 정보 인덱싱 실패")
                return False

        except Exception as e:
            print(f"❌ 직원 데이터 인덱싱 실패: {e}")
            return False

    def recommend_assignee_with_rag(
        self, task_description: str, meeting_context: str = ""
    ) -> dict:
        """RAG 기반 담당자 추천 (직원 전용 인덱스 사용)"""
        try:
            from services.search_service import search_staff_for_task

            # 1. 직원 전용 인덱스에서 적합한 직원 검색
            staff_results = search_staff_for_task(task_description, top_k=5)

            if not staff_results:
                print("⚠️ RAG 검색 결과 없음, 기존 방식으로 폴백")
                # 폴백: 기존 방식 사용
                return self.recommend_assignee_for_task(task_description)

            # 2. 검색된 직원 정보를 OpenAI에 제공하여 최적 담당자 추천
            staff_info = []
            for result in staff_results[:3]:  # 상위 3명만 사용
                staff_info.append(
                    {
                        "user_id": result.get("user_id"),
                        "name": result.get("name"),
                        "department": result.get("department"),
                        "position": result.get("position"),
                        "skills": result.get("skills", []),
                        "search_score": result.get("search_score", 0),
                    }
                )

            # 3. OpenAI에 컨텍스트와 함께 최적 담당자 요청
            from services.openai_service import recommend_best_assignee

            print(f"🔍 RAG 검색 결과: {len(staff_results)}명 후보")
            return recommend_best_assignee(
                task_description, staff_info, meeting_context
            )

        except Exception as e:
            print(f"❌ RAG 기반 담당자 추천 실패: {e}")
            # 폴백: 기존 방식 사용
            return self.recommend_assignee_for_task(task_description)

        except Exception as e:
            print(f"RAG 기반 담당자 추천 실패: {e}")
            # 폴백: 기존 방식 사용
            return self.recommend_assignee_for_task(task_description)


# 전역 서비스 매니저 인스턴스
service_manager = ServiceManager()
