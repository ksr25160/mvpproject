from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchIndexer,
    SearchIndexerDataContainer,
    SearchIndexerDataSourceConnection,
)
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError, ResourceNotFoundError
import config.config as config
import time
import logging
from config.logging_config import (
    log_error_with_context,
    log_performance,
    log_azure_service_call,
)

# 로깅 설정
logger = logging.getLogger("search_service")


def create_search_index():
    """AI Search 인덱스가 없는 경우 생성합니다."""
    try:
        logger.info("AI Search 인덱스 생성/확인 시작")

        index_client = SearchIndexClient(
            endpoint=config.AZURE_SEARCH_ENDPOINT,
            credential=AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY),
        )

        # 회의 문서용 인덱스 확인/생성
        meeting_index_exists = create_meetings_index(index_client)

        # 직원 전용 인덱스 확인/생성
        staff_index_exists = create_staff_index(index_client)

        return meeting_index_exists and staff_index_exists

    except Exception as e:
        logger.error(f"AI Search 인덱스 생성 실패: {e}")
        return False


def create_meetings_index(index_client):
    """회의 문서용 인덱스를 생성합니다."""
    try:
        # 기존 인덱스 확인
        try:
            existing_index = index_client.get_index(config.AZURE_SEARCH_INDEX)
            logger.info(
                f"✅ 회의 문서 인덱스가 이미 존재합니다: {config.AZURE_SEARCH_INDEX}"
            )
            return True
        except ResourceNotFoundError:
            logger.info(
                f"회의 문서 인덱스가 존재하지 않아 새로 생성합니다: {config.AZURE_SEARCH_INDEX}"
            )

            # 11개 필드 인덱스 정의 (improve_index.py와 동일)
            fields = [
                SimpleField(name="id", type="Edm.String", key=True),
                SearchableField(name="content", type="Edm.String", searchable=True),
                SearchableField(
                    name="meeting_title", type="Edm.String", searchable=True
                ),
                SearchableField(name="summary", type="Edm.String", searchable=True),
                SimpleField(
                    name="meeting_id",
                    type="Edm.String",
                    searchable=False,
                    filterable=True,
                ),
                SimpleField(
                    name="action_items_count",
                    type="Edm.Int32",
                    searchable=False,
                    filterable=True,
                ),
                SimpleField(
                    name="created_at",
                    type="Edm.String",
                    searchable=False,
                    filterable=True,
                ),
                SearchableField(
                    name="participants", type="Edm.String", searchable=True
                ),
                SearchableField(name="keywords", type="Edm.String", searchable=True),
                SimpleField(
                    name="blob_path",
                    type="Edm.String",
                    searchable=False,
                    filterable=True,
                ),
                SimpleField(name="document_type", type="Edm.String", filterable=True),
            ]

            index = SearchIndex(name=config.AZURE_SEARCH_INDEX, fields=fields)

            # 인덱스 생성
            result = index_client.create_index(index)
            logger.info(
                f"✅ 회의 문서 인덱스 생성 완료 (11필드): {config.AZURE_SEARCH_INDEX}"
            )

            return True

    except Exception as e:
        logger.error(f"회의 문서 인덱스 생성 실패: {e}")
        return False


def create_staff_index(index_client):
    """직원 전용 인덱스를 생성합니다."""
    try:
        # 기존 인덱스 확인
        try:
            existing_index = index_client.get_index(config.AZURE_SEARCH_STAFF_INDEX)
            logger.info(
                f"✅ 직원 인덱스가 이미 존재합니다: {config.AZURE_SEARCH_STAFF_INDEX}"
            )
            return True
        except ResourceNotFoundError:
            logger.info(
                f"직원 인덱스가 존재하지 않아 새로 생성합니다: {config.AZURE_SEARCH_STAFF_INDEX}"
            )

        # 새로운 인덱스 생성
        logger.info(f"📝 새로운 직원 인덱스 생성 중: {config.AZURE_SEARCH_STAFF_INDEX}")

        # 직원 전용 인덱스 정의 (배열 필드 제거)
        fields = [
            SimpleField(name="id", type="Edm.String", key=True),
            SimpleField(
                name="user_id", type="Edm.Int32", searchable=False, filterable=True
            ),
            SearchableField(name="name", type="Edm.String", searchable=True),
            SearchableField(
                name="department",
                type="Edm.String",
                searchable=True,
                filterable=True,
            ),
            SearchableField(name="position", type="Edm.String", searchable=True),
            SearchableField(name="email", type="Edm.String", searchable=True),
            SearchableField(
                name="skills_text", type="Edm.String", searchable=True
            ),  # 스킬을 텍스트로 저장
            SimpleField(name="created_at", type="Edm.String", searchable=False),
            SimpleField(name="updated_at", type="Edm.String", searchable=False),
        ]

        index = SearchIndex(name=config.AZURE_SEARCH_STAFF_INDEX, fields=fields)

        # 인덱스 생성
        result = index_client.create_index(index)
        logger.info(f"✅ 직원 인덱스 생성 완료: {config.AZURE_SEARCH_STAFF_INDEX}")

        return True

    except Exception as e:
        logger.error(f"직원 인덱스 생성 실패: {e}")
        return False


def recreate_staff_index():
    """직원 인덱스를 강제로 재생성합니다 (문제 해결용)."""
    try:
        logger.info("직원 인덱스 강제 재생성 시작")

        index_client = SearchIndexClient(
            endpoint=config.AZURE_SEARCH_ENDPOINT,
            credential=AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY),
        )

        # 기존 인덱스 삭제
        try:
            index_client.delete_index(config.AZURE_SEARCH_STAFF_INDEX)
            logger.info(
                f"🗑️ 기존 직원 인덱스 삭제 완료: {config.AZURE_SEARCH_STAFF_INDEX}"
            )
        except ResourceNotFoundError:
            logger.info(f"삭제할 직원 인덱스가 없음: {config.AZURE_SEARCH_STAFF_INDEX}")

        # 잠시 대기 (Azure 리소스 정리 시간)
        import time

        time.sleep(2)

        # 새 인덱스 생성
        return create_staff_index(index_client)

    except Exception as e:
        logger.error(f"직원 인덱스 재생성 실패: {e}")
        return False

    except Exception as e:
        logger.error(f"❌ AI Search 인덱스 생성 실패: {e}")
        return False


def create_blob_indexer():
    """Blob Storage용 Indexer를 생성합니다."""
    try:
        logger.info("Blob Storage Indexer 생성/확인 시작")

        index_client = SearchIndexClient(
            endpoint=config.AZURE_SEARCH_ENDPOINT,
            credential=AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY),
        )

        # Data Source 생성
        datasource_name = f"{config.AZURE_SEARCH_INDEX}-datasource"
        try:
            # 기존 데이터 소스 확인
            existing_datasource = index_client.get_data_source_connection(
                datasource_name
            )
            logger.info(f"✅ 데이터 소스가 이미 존재합니다: {datasource_name}")
        except ResourceNotFoundError:
            # 데이터 소스 생성
            container = SearchIndexerDataContainer(name="meetings")
            datasource = SearchIndexerDataSourceConnection(
                name=datasource_name,
                type="azureblob",
                connection_string=f"DefaultEndpointsProtocol=https;AccountName={config.AZURE_STORAGE_ACCOUNT_NAME};AccountKey={config.AZURE_STORAGE_ACCOUNT_KEY};EndpointSuffix=core.windows.net",
                container=container,
            )
            index_client.create_data_source_connection(datasource)
            logger.info(f"✅ 데이터 소스 생성 완료: {datasource_name}")

        # Indexer 생성
        indexer_name = f"{config.AZURE_SEARCH_INDEX}-indexer"
        try:
            # 기존 Indexer 확인
            existing_indexer = index_client.get_indexer(indexer_name)
            logger.info(f"✅ Indexer가 이미 존재합니다: {indexer_name}")
        except ResourceNotFoundError:
            # Indexer 생성
            indexer = SearchIndexer(
                name=indexer_name,
                data_source_name=datasource_name,
                target_index_name=config.AZURE_SEARCH_INDEX,
            )
            index_client.create_indexer(indexer)
            logger.info(f"✅ Indexer 생성 완료: {indexer_name}")

        return True

    except Exception as e:
        logger.warning(f"⚠️ Blob Storage Indexer 생성 실패 (수동 인덱싱으로 계속): {e}")
        return False


def setup_search_infrastructure():
    """AI Search 인프라를 완전히 설정합니다 (Index + Indexer)."""
    try:
        logger.info("AI Search 인프라 전체 설정 시작")

        # 1. Index 생성
        if not create_search_index():
            logger.error("Index 생성 실패")
            return False

        # 2. Blob Indexer 생성 (선택적)
        if (
            hasattr(config, "AZURE_STORAGE_ACCOUNT_NAME")
            and config.AZURE_STORAGE_ACCOUNT_NAME
        ):
            create_blob_indexer()
        else:
            logger.info("Blob Storage 설정이 없어 수동 인덱싱 방식을 사용합니다")

        logger.info("✅ AI Search 인프라 설정 완료")
        return True

    except Exception as e:
        logger.error(f"❌ AI Search 인프라 설정 실패: {e}")
        return False


def index_document(doc_id, content, metadata, blob_path=None):
    """문서를 Azure AI Search 인덱스에 추가합니다."""
    start_time = time.time()
    try:
        logger.info(f"AI Search 인덱싱 시작: {doc_id}")

        # 인덱스 존재 확인 및 생성
        if not setup_search_infrastructure():
            raise Exception("AI Search 인프라 설정에 실패했습니다.")

        search_client = SearchClient(
            endpoint=config.AZURE_SEARCH_ENDPOINT,
            index_name=config.AZURE_SEARCH_INDEX,
            credential=AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY),
        )

        doc = {
            "id": doc_id,
            "content": content,
            "meeting_title": metadata.get("title", "") if metadata else "",
            "summary": metadata.get("summary", "") if metadata else "",
            "meeting_id": metadata.get("meeting_id", "") if metadata else "",
            "action_items_count": (
                metadata.get("action_items_count", 0) if metadata else 0
            ),
            "created_at": metadata.get("created_at", "") if metadata else "",
            "participants": metadata.get("participants", "") if metadata else "",
            "keywords": metadata.get("keywords", "") if metadata else "",
            "document_type": metadata.get("document_type", "") if metadata else "",
        }

        # Blob 경로가 제공된 경우 추가
        if blob_path:
            doc["blob_path"] = blob_path

        result = search_client.upload_documents(documents=[doc])

        duration = time.time() - start_time
        log_azure_service_call(
            logger,
            "Azure AI Search",
            "upload_documents",
            duration,
            True,
            None,
            f"Document ID: {doc_id}",
        )
        log_performance(
            logger,
            "document_indexing",
            duration,
            f"Content length: {len(content)} characters",
        )

        logger.info(f"✅ AI Search 인덱싱 완료: {doc_id}")

    except AzureError as e:
        duration = time.time() - start_time
        log_error_with_context(
            logger, e, f"Azure AI Search error indexing document: {doc_id}"
        )
        log_azure_service_call(
            logger,
            "Azure AI Search",
            "upload_documents",
            duration,
            False,
            None,
            f"Azure Error: {str(e)}",
        )
        logger.error(f"❌ AI Search 인덱싱 실패 (Azure 오류): {doc_id} - {e}")
        raise

    except Exception as e:
        duration = time.time() - start_time
        log_error_with_context(
            logger, e, f"Unexpected error indexing document: {doc_id}"
        )
        log_azure_service_call(
            logger,
            "Azure AI Search",
            "upload_documents",
            duration,
            False,
            None,
            f"Unexpected error: {str(e)}",
        )
        logger.error(f"❌ AI Search 인덱싱 중 예상치 못한 오류: {doc_id} - {e}")
        raise


def search_documents(query: str, top: int = 3):
    """Azure AI Search에서 문서를 검색합니다."""
    start_time = time.time()
    try:
        logger.info(f"AI Search 쿼리 실행: '{query}' (top {top})")

        # 인덱스 존재 확인 및 생성
        if not setup_search_infrastructure():
            raise Exception("AI Search 인프라 설정에 실패했습니다.")

        search_client = SearchClient(
            endpoint=config.AZURE_SEARCH_ENDPOINT,
            index_name=config.AZURE_SEARCH_INDEX,
            credential=AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY),
        )

        results = search_client.search(query, top=top)
        docs = []

        for r in results:
            docs.append(
                {
                    "id": r["id"],
                    "content": r["content"],
                    "metadata": r.get("metadata", {}),
                }
            )

        duration = time.time() - start_time
        log_azure_service_call(
            logger,
            "Azure AI Search",
            "search",
            duration,
            True,
            None,
            f"Query: '{query}', Results: {len(docs)}",
        )
        log_performance(
            logger,
            "document_search",
            duration,
            f"Query: '{query}', Results: {len(docs)}",
        )

        logger.info(f"✅ AI Search 검색 완료: {len(docs)}개 결과 반환")
        return docs

    except AzureError as e:
        duration = time.time() - start_time
        log_error_with_context(logger, e, f"Azure AI Search error searching: {query}")
        log_azure_service_call(
            logger,
            "Azure AI Search",
            "search",
            duration,
            False,
            None,
            f"Azure Error: {str(e)}",
        )
        logger.error(f"❌ AI Search 검색 실패 (Azure 오류): {query} - {e}")
        raise

    except Exception as e:
        duration = time.time() - start_time
        log_error_with_context(logger, e, f"Unexpected error searching: {query}")
        log_azure_service_call(
            logger,
            "Azure AI Search",
            "search",
            duration,
            False,
            None,
            f"Unexpected error: {str(e)}",
        )
        logger.error(f"❌ AI Search 검색 중 예상치 못한 오류: {query} - {e}")
        raise


def index_staff_data_to_search(staff_list):
    """직원 정보를 직원 전용 인덱스에 저장합니다 (업데이트 방식)."""
    start_time = time.time()

    try:
        search_client = SearchClient(
            endpoint=config.AZURE_SEARCH_ENDPOINT,
            index_name=config.AZURE_SEARCH_STAFF_INDEX,
            credential=AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY),
        )

        # 기존 직원 데이터 삭제 (완전 새로고침)
        try:
            # 모든 기존 직원 데이터 조회
            search_results = search_client.search("*", select="id")
            existing_ids = [result["id"] for result in search_results]

            # 기존 데이터 삭제
            if existing_ids:
                delete_docs = [
                    {"@search.action": "delete", "id": doc_id}
                    for doc_id in existing_ids
                ]
                search_client.upload_documents(documents=delete_docs)
                logger.info(f"🗑️ 기존 직원 데이터 {len(existing_ids)}개 삭제 완료")
        except Exception as delete_error:
            logger.warning(
                f"⚠️ 기존 직원 데이터 삭제 중 오류 (계속 진행): {delete_error}"
            )

        # 새로운 직원 데이터 추가
        staff_docs = []
        for staff in staff_list:
            # 스킬을 문자열로 변환 (검색용)
            skills_text = ", ".join(staff.get("skills", []))

            doc = {
                "@search.action": "upload",
                "id": staff["id"],
                "user_id": staff.get("user_id"),
                "name": staff.get("name", ""),
                "department": staff.get("department", ""),
                "position": staff.get("position", ""),
                "email": staff.get("email", ""),
                "skills_text": skills_text,
                "created_at": str(staff.get("created_at", "")),
                "updated_at": str(staff.get("updated_at", "")),
            }
            staff_docs.append(doc)

        if staff_docs:
            result = search_client.upload_documents(documents=staff_docs)

            duration = time.time() - start_time
            log_azure_service_call(
                logger,
                "Azure AI Search",
                "index_staff_data",
                duration,
                True,
                None,
                f"Indexed {len(staff_docs)} staff records",
            )
            log_performance(
                logger, "staff_indexing", duration, f"Staff count: {len(staff_docs)}"
            )

            logger.info(f"✅ 직원 정보 인덱싱 완료: {len(staff_docs)}명")
            return True
        else:
            logger.warning("⚠️ 인덱싱할 직원 정보가 없습니다")
            return False

    except AzureError as e:
        duration = time.time() - start_time
        log_error_with_context(logger, e, "Azure AI Search error indexing staff data")
        log_azure_service_call(
            logger,
            "Azure AI Search",
            "index_staff_data",
            duration,
            False,
            None,
            f"Azure Error: {str(e)}",
        )
        logger.error(f"❌ 직원 정보 인덱싱 실패 (Azure 오류): {e}")
        raise

    except Exception as e:
        duration = time.time() - start_time
        log_error_with_context(logger, e, "Failed to index staff data")
        log_azure_service_call(
            logger, "Azure AI Search", "index_staff_data", duration, False, None, str(e)
        )
        logger.error(f"❌ 직원 정보 인덱싱 실패: {e}")
        raise


def expand_task_keywords(task_description):
    """업무 설명을 검색 친화적인 키워드로 확장합니다."""
    keywords = set([task_description])  # 원본도 포함

    # 업무 유형별 키워드 매핑
    task_keywords = {
        # 재무/회계 관련
        "세금": ["세무", "회계", "재무", "과세", "신고", "정산", "엔테이션", "지표"],
        "지표": [
            "분석",
            "데이터",
            "통계",
            "리포트",
            "보고서",
            "성과",
            "세금",
            "엔테이션",
        ],
        "예산": ["재무", "회계", "비용", "지출", "예산"],
        "결산": ["회계", "재무", "정산", "마감"],
        "엔테이션": ["세금", "지표", "분석", "데이터", "세무"],
        # 개발 관련
        "시스템": ["개발", "프로그래밍", "코딩", "IT", "소프트웨어"],
        "개발": ["프로그래밍", "코딩", "시스템", "IT", "소프트웨어"],
        "API": ["개발", "프로그래밍", "백엔드", "시스템", "백앤드"],
        "백엔드": ["API", "개발", "시스템", "서버", "백앤드"],
        "백앤드": ["백엔드", "API", "개발", "시스템", "서버"],
        "데이터베이스": ["개발", "DB", "시스템", "백엔드"],
        "배포": ["개발", "시스템", "운영", "릴리즈", "출시"],
        # QA/테스트 관련
        "QA": ["테스트", "품질", "검증", "시나리오", "검사"],
        "테스트": ["QA", "품질", "검증", "시나리오", "검사"],
        "시나리오": ["테스트", "QA", "품질", "케이스"],
        # A/B 테스트 관련
        "AB": ["테스트", "실험", "분석", "개선", "최적화"],
        "A/B": ["AB", "테스트", "실험", "분석"],
        # 마케팅 관련
        "캠페인": ["마케팅", "홍보", "광고", "프로모션"],
        "홍보": ["마케팅", "캠페인", "광고", "PR"],
        "고객": ["마케팅", "CS", "서비스", "관리"],
        "랜딩": ["페이지", "웹", "사이트", "UI"],
        # 디자인 관련
        "UI": ["디자인", "UX", "인터페이스", "화면"],
        "UX": ["디자인", "UI", "사용자", "경험"],
        "디자인": ["UI", "UX", "그래픽", "시각"],
        "페이지": ["웹", "사이트", "UI", "랜딩"],
        # 기획 관련
        "기획": ["계획", "전략", "관리", "PM"],
        "전략": ["기획", "계획", "관리", "방향"],
        "관리": ["기획", "PM", "운영", "조정"],
        "준비": ["계획", "기획", "설정", "구성"],
        "설정": ["구성", "설치", "준비", "배치"],
    }

    # 업무 설명에서 키워드 찾아서 확장
    description_lower = task_description.lower()
    for main_keyword, expansions in task_keywords.items():
        if main_keyword in description_lower:
            keywords.update(expansions)
            keywords.add(main_keyword)

    # 일반적인 업무 관련 단어들도 추가 검색
    general_expansions = {
        "결정": ["승인", "검토", "확정", "완료"],
        "완료": ["마무리", "종료", "제출", "정리", "준비"],
        "검토": ["확인", "점검", "검증", "승인"],
        "작성": ["생성", "제작", "개발", "구성"],
        "제출": ["완료", "전달", "송부", "업로드"],
        "준비": ["완료", "설정", "구성", "기획"],
    }

    for word, expansions in general_expansions.items():
        if word in description_lower:
            keywords.update(expansions)

    return " OR ".join(list(keywords))


def search_staff_for_task(task_description, top_k=5):
    """작업 설명을 기반으로 직원 전용 인덱스에서 적합한 직원을 검색합니다."""
    start_time = time.time()

    try:
        search_client = SearchClient(
            endpoint=config.AZURE_SEARCH_ENDPOINT,
            index_name=config.AZURE_SEARCH_STAFF_INDEX,
            credential=AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY),
        )

        # 직원 검색용 특별 키워드 매핑 (간단하고 직접적)
        staff_keyword_map = {
            "개발": [
                "개발자",
                "developer",
                "개발팀",
                "backend",
                "frontend",
                "javascript",
                "python",
                "react",
                "typescript",
            ],
            "백엔드": ["backend", "개발자", "developer", "API", "서버", "python"],
            "백앤드": ["backend", "개발자", "developer", "API", "서버", "python"],
            "프론트": [
                "frontend",
                "개발자",
                "developer",
                "UI",
                "웹",
                "react",
                "typescript",
                "javascript",
                "프론트엔드",
            ],
            "프론트엔드": [
                "frontend",
                "개발자",
                "developer",
                "UI",
                "웹",
                "react",
                "typescript",
                "javascript",
                "프론트",
            ],
            "react": ["react", "frontend", "프론트엔드", "개발자", "javascript"],
            "QA": ["QA", "테스트", "품질", "엔지니어", "자동화"],
            "테스트": ["QA", "테스트", "품질", "엔지니어", "자동화", "selenium"],
            "자동화": ["자동화", "테스트", "QA", "selenium", "CI/CD"],
            "마케팅": [
                "마케터",
                "마케팅팀",
                "홍보",
                "캠페인",
                "SEO",
                "소셜미디어",
                "디지털",
            ],
            "SEO": ["SEO", "마케팅", "디지털", "검색", "최적화"],
            "기획": ["기획팀장", "기획팀", "PM", "계획", "서비스", "제품"],
            "데이터": [
                "데이터",
                "분석가",
                "데이터팀",
                "통계",
                "빅데이터",
                "ETL",
                "엔지니어",
            ],
            "빅데이터": ["빅데이터", "데이터", "엔지니어", "ETL", "spark"],
            "ETL": ["ETL", "데이터", "엔지니어", "빅데이터"],
            "디자인": [
                "디자인",
                "디자이너",
                "UI",
                "UX",
                "사용자",
                "인터페이스",
                "프로토타입",
            ],
            "UI": ["UI", "디자인", "디자이너", "인터페이스", "사용자"],
            "UX": ["UX", "디자인", "디자이너", "사용자", "경험"],
            "인프라": [
                "인프라",
                "DevOps",
                "CI/CD",
                "Azure",
                "배포",
                "모니터링",
                "서버",
            ],
            "DevOps": ["DevOps", "인프라", "CI/CD", "배포", "자동화", "Azure"],
            "배포": ["배포", "DevOps", "인프라", "CI/CD"],
        }

        # 키워드 확장
        keywords = [task_description]
        task_lower = task_description.lower()

        for key, values in staff_keyword_map.items():
            if key in task_lower:
                keywords.extend(values)

        # OR 검색 쿼리 생성
        search_query = " OR ".join(keywords)
        logger.info(f"🔍 원본 쿼리: {task_description}")
        logger.info(f"🔍 직원 검색 쿼리: {search_query}")

        results = search_client.search(
            search_text=search_query,
            top=top_k,
            select=[
                "id",
                "user_id",
                "name",
                "department",
                "position",
                "skills_text",
            ],
            search_mode="any",  # OR 검색으로 변경
        )

        staff_results = []
        for result in results:
            # skills_text를 다시 배열로 변환 (호환성 유지)
            skills_text = result.get("skills_text", "")
            skills = [s.strip() for s in skills_text.split(",")] if skills_text else []

            staff_data = {
                "id": result["id"],
                "user_id": result.get("user_id"),
                "name": result.get("name", ""),
                "department": result.get("department", ""),
                "position": result.get("position", ""),
                "skills": skills,
                "search_score": result.get("@search.score", 0),
            }
            staff_results.append(staff_data)

        duration = time.time() - start_time
        log_azure_service_call(
            logger,
            "Azure AI Search",
            "search_staff",
            duration,
            True,
            None,
            f"Found {len(staff_results)} staff members",
        )
        log_performance(
            logger,
            "staff_search",
            duration,
            f"Query: '{task_description}', Results: {len(staff_results)}",
        )

        logger.info(f"✅ 직원 검색 완료: {len(staff_results)}명 발견")
        return staff_results

    except AzureError as e:
        duration = time.time() - start_time
        log_error_with_context(
            logger, e, f"Azure AI Search error searching staff: {task_description}"
        )
        log_azure_service_call(
            logger,
            "Azure AI Search",
            "search_staff",
            duration,
            False,
            None,
            f"Azure Error: {str(e)}",
        )
        logger.error(f"❌ 직원 검색 실패 (Azure 오류): {e}")
        return []

    except Exception as e:
        duration = time.time() - start_time
        log_error_with_context(logger, e, f"Failed to search staff: {task_description}")
        log_azure_service_call(
            logger, "Azure AI Search", "search_staff", duration, False, None, str(e)
        )
        logger.error(f"❌ 직원 검색 실패: {e}")
        return []


def clean_legacy_staff_data_from_meetings_index():
    """기존 meetings-index에서 직원 데이터를 제거합니다."""
    start_time = time.time()

    try:
        search_client = SearchClient(
            endpoint=config.AZURE_SEARCH_ENDPOINT,
            index_name=config.AZURE_SEARCH_INDEX,
            credential=AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY),
        )

        # 직원 데이터 검색 (staff_로 시작하는 ID)
        search_results = search_client.search(
            "*", select="id", filter="id eq 'staff_*'"
        )
        staff_ids = []

        # 모든 결과를 확인하여 직원 데이터 찾기
        all_results = search_client.search("*", select="id")
        for result in all_results:
            doc_id = result.get("id", "")
            if doc_id.startswith("staff_"):
                staff_ids.append(doc_id)

        # 직원 데이터 삭제
        if staff_ids:
            delete_docs = [
                {"@search.action": "delete", "id": doc_id} for doc_id in staff_ids
            ]
            search_client.upload_documents(documents=delete_docs)

            duration = time.time() - start_time
            log_azure_service_call(
                logger,
                "Azure AI Search",
                "clean_staff_data",
                duration,
                True,
                None,
                f"Removed {len(staff_ids)} staff records",
            )

            logger.info(f"✅ 기존 인덱스에서 직원 데이터 {len(staff_ids)}개 제거 완료")
            return True
        else:
            logger.info("📋 기존 인덱스에 제거할 직원 데이터가 없습니다")
            return True

    except Exception as e:
        duration = time.time() - start_time
        log_error_with_context(
            logger, e, "Failed to clean staff data from meetings index"
        )
        log_azure_service_call(
            logger, "Azure AI Search", "clean_staff_data", duration, False, None, str(e)
        )
        logger.error(f"❌ 기존 인덱스 직원 데이터 제거 실패: {e}")
        return False


async def ask_question_with_search(question: str, max_results: int = 3) -> str:
    """
    Azure AI Search를 사용하여 관련 문서를 찾고 OpenAI로 답변을 생성합니다.
    질문 유형에 따라 회의록 또는 직원 인덱스를 선택합니다.

    Args:
        question: 사용자 질문
        max_results: 검색할 최대 문서 수

    Returns:
        AI가 생성한 답변
    """
    try:
        start_time = time.time()
        logger.info(f"RAG 검색 시작: {question[:50]}...")

        # 1. 질문 유형 분석 - 담당자/직원 관련 질문인지 확인
        staff_keywords = [
            "담당자",
            "개발자",
            "마케터",
            "누가",
            "누구",
            "직원",
            "팀원",
            "사람",
            "추천",
            "맡",
            "적합",
        ]
        is_staff_question = any(keyword in question for keyword in staff_keywords)

        logger.info(f"질문 유형: {'직원 검색' if is_staff_question else '회의록 검색'}")

        # 2. 키워드 확장으로 검색 쿼리 개선 (단순화)
        if is_staff_question:
            # 직원 검색은 원본 질문 + 간단한 키워드만 사용
            simple_keywords = []
            if "개발" in question or "백앤드" in question or "백엔드" in question:
                simple_keywords.extend(
                    ["개발", "개발자", "developer", "backend", "javascript", "python"]
                )
            if "마케팅" in question:
                simple_keywords.extend(["마케팅", "마케터", "marketing", "campaign"])
            if "QA" in question or "테스트" in question:
                simple_keywords.extend(["QA", "테스트", "test", "quality"])
            if "프론트" in question:
                simple_keywords.extend(["프론트", "frontend", "UI", "UX"])

            if simple_keywords:
                expanded_query = f"{question} OR {' OR '.join(simple_keywords)}"
            else:
                expanded_query = question
        else:
            # 회의록 검색은 기존 확장 시스템 사용
            expanded_query = expand_task_keywords(question)

        logger.info(f"확장된 검색 쿼리: {expanded_query}")

        # 3. 질문 유형에 따라 적절한 인덱스 선택
        if is_staff_question:
            # 직원 인덱스에서 검색
            search_client = SearchClient(
                endpoint=config.AZURE_SEARCH_ENDPOINT,
                index_name=config.AZURE_SEARCH_STAFF_INDEX,
                credential=AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY),
            )

            # 직원 검색 실행
            search_results = search_client.search(
                search_text=expanded_query,
                top=max_results,
                select=["name", "department", "position", "skills_text"],
                search_mode="any",
            )

            results_list = list(search_results)

            # 직원 정보를 컨텍스트로 변환
            contexts = []
            for result in results_list:
                context_parts = []

                name = result.get("name")
                department = result.get("department")
                position = result.get("position")
                skills = result.get("skills_text")

                if name:
                    context_parts.append(f"이름: {name}")
                if department:
                    context_parts.append(f"부서: {department}")
                if position:
                    context_parts.append(f"직책: {position}")
                if skills:
                    context_parts.append(f"기술/경험: {skills}")

                contexts.append("\n".join(context_parts))

        else:
            # 회의록 인덱스에서 검색
            search_client = SearchClient(
                endpoint=config.AZURE_SEARCH_ENDPOINT,
                index_name=config.AZURE_SEARCH_INDEX,
                credential=AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY),
            )

            # 먼저 확장된 쿼리로 검색 시도
            search_results = search_client.search(
                search_text=expanded_query,
                top=max_results,
                select=["content", "meeting_title", "summary", "meeting_id"],
                search_mode="any",
            )

            # 결과가 없으면 원본 질문으로 다시 검색
            results_list = list(search_results)
            if not results_list:
                logger.info("확장된 쿼리로 결과 없음, 원본 질문으로 재검색")
                search_results = search_client.search(
                    search_text=question,
                    top=max_results,
                    select=["content", "meeting_title", "summary", "meeting_id"],
                    search_mode="any",
                )
                results_list = list(search_results)

            # 여전히 결과가 없으면 전체 문서 검색
            if not results_list:
                logger.info("원본 질문으로도 결과 없음, 전체 문서에서 검색")
                search_results = search_client.search(
                    search_text="*",
                    top=1,
                    select=["content", "meeting_title", "summary", "meeting_id"],
                )
                results_list = list(search_results)

            # 회의록 정보를 컨텍스트로 변환
            contexts = []
            for result in results_list:
                context_parts = []

                # 회의 제목
                meeting_title = result.get("meeting_title")
                if meeting_title:
                    context_parts.append(f"회의: {meeting_title}")

                # 요약
                summary = result.get("summary")
                if summary:
                    context_parts.append(f"요약: {summary}")

                # 전체 내용 (일부만)
                if result.get("content"):
                    content = result["content"][:1000]
                    context_parts.append(f"내용: {content}")

                contexts.append("\n".join(context_parts))

        logger.info(f"검색 결과: {len(contexts)}개 컨텍스트 생성")

        if not contexts:
            if is_staff_question:
                return "죄송합니다. 질문과 관련된 담당자 정보를 찾을 수 없습니다."
            else:
                return "죄송합니다. 질문과 관련된 회의록을 찾을 수 없습니다."

        # 4. OpenAI API를 사용하여 답변 생성
        from openai import AzureOpenAI

        client = AzureOpenAI(
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION or "2024-02-01",
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
        )
        combined_context = "\n\n---\n\n".join(contexts)

        # 질문 유형에 따라 다른 프롬프트 사용
        if is_staff_question:
            prompt = f"""다음은 직원 정보입니다:

{combined_context}

사용자 질문: {question}

위의 직원 정보를 바탕으로 사용자의 질문에 가장 적합한 담당자를 추천해주세요.
담당자의 이름, 부서, 직책, 관련 기술/경험을 포함하여 왜 적합한지 설명해주세요.
만약 적합한 담당자가 없다면 "적합한 담당자를 찾을 수 없습니다"라고 답변해주세요.
답변은 한국어로 작성해주세요."""
        else:
            prompt = f"""다음은 회의록에서 검색된 관련 정보입니다:

{combined_context}

사용자 질문: {question}

위의 회의록 정보를 바탕으로 사용자의 질문에 대해 정확하고 도움이 되는 답변을 제공해주세요. 
만약 회의록에 관련 정보가 없다면 "회의록에서 해당 정보를 찾을 수 없습니다"라고 답변해주세요.
답변은 한국어로 작성해주세요."""

        response = client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": "당신은 회의록 분석 및 담당자 추천 전문가입니다. 제공된 정보를 바탕으로 정확하고 유용한 답변을 제공합니다.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=1000,
            temperature=0.3,
        )

        answer = response.choices[0].message.content.strip()

        duration = time.time() - start_time
        log_performance(
            logger,
            "rag_search_complete",
            duration,
            {
                "question_length": len(question),
                "results_count": len(contexts),
                "answer_length": len(answer),
                "search_type": "staff" if is_staff_question else "meeting",
            },
        )

        logger.info(
            f"✅ RAG 검색 완료 ({duration:.2f}초): {len(contexts)}개 문서에서 답변 생성 ({'직원' if is_staff_question else '회의록'} 검색)"
        )
        return answer

    except Exception as e:
        duration = time.time() - start_time
        log_error_with_context(
            logger, e, f"RAG search failed for question: {question[:100]}"
        )
        logger.error(f"❌ RAG 검색 실패 ({duration:.2f}초): {e}")
        return f"죄송합니다. 검색 중 오류가 발생했습니다: {str(e)}"


def search_meetings(query: str, max_results: int = 5) -> list:
    """
    회의록에서 키워드로 검색합니다.

    Args:
        query: 검색 쿼리
        max_results: 최대 결과 수

    Returns:
        검색 결과 리스트
    """
    try:
        start_time = time.time()
        logger.info(f"회의록 검색: {query}")

        # 키워드 확장
        expanded_query = expand_task_keywords(query)

        search_client = SearchClient(
            endpoint=config.AZURE_SEARCH_ENDPOINT,
            index_name=config.AZURE_SEARCH_INDEX,
            credential=AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY),
        )

        search_results = search_client.search(
            search_text=expanded_query,
            top=max_results,
            select=["meeting_id", "meeting_title", "summary", "created_at"],
            search_mode="all",
        )

        results = []
        for result in search_results:
            results.append(
                {
                    "meeting_id": result.get("meeting_id"),
                    "meeting_title": result.get("meeting_title"),
                    "summary": result.get("summary"),
                    "created_at": result.get("created_at"),
                    "score": result.get("@search.score", 0),
                }
            )

        duration = time.time() - start_time
        logger.info(f"✅ 회의록 검색 완료 ({duration:.2f}초): {len(results)}개 결과")

        return results

    except Exception as e:
        duration = time.time() - start_time
        log_error_with_context(logger, e, f"Meeting search failed for: {query}")
        logger.error(f"❌ 회의록 검색 실패 ({duration:.2f}초): {e}")
        return []
