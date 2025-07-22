from services.openai_service import (
    transcribe_audio, summarize_and_extract, apply_json_modification,
    ask_question, ask_question_with_search
)
from services.search_service import index_document, search_documents
from services.blob_service import upload_to_blob

class SpeechAgent:
    """음성 파일을 텍스트로 변환하는 에이전트"""
    def transcribe(self, file_path: str) -> str:
        return transcribe_audio(file_path)

class SummarizationAgent:
    """회의록 요약 및 액션아이템 추출 에이전트"""
    def summarize(self, text: str) -> dict:
        return summarize_and_extract(text)

class ModificationAgent:
    """요약/액션아이템 결과를 자연어로 수정하는 에이전트"""
    def modify(self, original_json: str, mod_request: str) -> dict:
        return apply_json_modification(original_json, mod_request)

class SearchAgent:
    """Azure AI Search 인덱싱 및 검색 에이전트"""
    def index(self, doc_id, content, metadata):
        return index_document(doc_id, content, metadata)
    def search(self, query: str, top: int = 3):
        return search_documents(query, top)

class BlobAgent:
    """Blob Storage 업로드 에이전트"""
    def upload(self, file_path, blob_name):
        return upload_to_blob(file_path, blob_name)

class QAAgent:
    """회의록/액션아이템 질의응답 에이전트"""
    def answer(self, all_text: str, question: str) -> str:
        return ask_question(all_text, question)
    def answer_with_search(self, query: str) -> str:
        return ask_question_with_search(query)

class AgentOrchestrator:
    """멀티 에이전트 오케스트레이터"""
    def __init__(self):
        self.speech = SpeechAgent()
        self.summarizer = SummarizationAgent()
        self.modifier = ModificationAgent()
        self.search = SearchAgent()
        self.blob = BlobAgent()
        self.qa = QAAgent()

    def process_audio_and_summarize(self, file_path: str):
        text = self.speech.transcribe(file_path)
        summary = self.summarizer.summarize(text)
        return summary

    def upload_and_index(self, file_path: str, blob_name: str, doc_id: str, metadata: dict):
        self.blob.upload(file_path, blob_name)
        content = self.speech.transcribe(file_path) if file_path.endswith(('.wav', '.mp3')) else open(file_path, encoding='utf-8').read()
        self.search.index(doc_id, content, metadata)

    def answer_question(self, question: str, use_search: bool = False):
        if use_search:
            return self.qa.answer_with_search(question)
        else:
            # 예시: 전체 회의록 텍스트를 받아야 함
            # 실제 사용 시 all_text 인자를 받아서 전달해야 함
            return self.qa.answer("", question)