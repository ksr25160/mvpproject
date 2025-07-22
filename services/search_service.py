from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchableField,
    SearchIndexer, SearchIndexerDataContainer, SearchIndexerDataSourceConnection
)
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError, ResourceNotFoundError
import config.config as config
import time
import logging
from config.logging_config import log_error_with_context, log_performance, log_azure_service_call

# 로깅 설정
logger = logging.getLogger("search_service")

def create_search_index():
    """AI Search 인덱스가 없는 경우 생성합니다."""
    try:
        logger.info("AI Search 인덱스 생성/확인 시작")
        
        index_client = SearchIndexClient(
            endpoint=config.AZURE_SEARCH_ENDPOINT,
            credential=AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY)
        )
        
        # 기존 인덱스 확인
        try:
            existing_index = index_client.get_index(config.AZURE_SEARCH_INDEX)
            logger.info(f"✅ AI Search 인덱스가 이미 존재합니다: {config.AZURE_SEARCH_INDEX}")
            return True
        except ResourceNotFoundError:
            logger.info(f"AI Search 인덱스가 존재하지 않아 새로 생성합니다: {config.AZURE_SEARCH_INDEX}")
            
            # 인덱스 정의
            fields = [
                SimpleField(name="id", type="Edm.String", key=True),
                SearchableField(name="content", type="Edm.String", searchable=True),
                SearchableField(name="metadata", type="Edm.String", searchable=True),
                SimpleField(name="blob_path", type="Edm.String", searchable=False, filterable=True)
            ]
            
            index = SearchIndex(name=config.AZURE_SEARCH_INDEX, fields=fields)
            
            # 인덱스 생성
            result = index_client.create_index(index)
            logger.info(f"✅ AI Search 인덱스 생성 완료: {config.AZURE_SEARCH_INDEX}")
            
            return True
        
    except Exception as e:
        logger.error(f"❌ AI Search 인덱스 생성 실패: {e}")
        return False

def create_blob_indexer():
    """Blob Storage용 Indexer를 생성합니다."""
    try:
        logger.info("Blob Storage Indexer 생성/확인 시작")
        
        index_client = SearchIndexClient(
            endpoint=config.AZURE_SEARCH_ENDPOINT,
            credential=AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY)
        )
        
        # Data Source 생성
        datasource_name = f"{config.AZURE_SEARCH_INDEX}-datasource"
        try:
            # 기존 데이터 소스 확인
            existing_datasource = index_client.get_data_source_connection(datasource_name)
            logger.info(f"✅ 데이터 소스가 이미 존재합니다: {datasource_name}")
        except ResourceNotFoundError:
            # 데이터 소스 생성
            container = SearchIndexerDataContainer(name="meetings")
            datasource = SearchIndexerDataSourceConnection(
                name=datasource_name,
                type="azureblob",
                connection_string=f"DefaultEndpointsProtocol=https;AccountName={config.AZURE_STORAGE_ACCOUNT_NAME};AccountKey={config.AZURE_STORAGE_ACCOUNT_KEY};EndpointSuffix=core.windows.net",
                container=container
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
                target_index_name=config.AZURE_SEARCH_INDEX
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
        if hasattr(config, 'AZURE_STORAGE_ACCOUNT_NAME') and config.AZURE_STORAGE_ACCOUNT_NAME:
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
            credential=AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY)
        )
        
        doc = {
            "id": doc_id,
            "content": content,
            "metadata": str(metadata) if metadata else ""
        }
        
        # Blob 경로가 제공된 경우 추가
        if blob_path:
            doc["blob_path"] = blob_path
        
        result = search_client.upload_documents(documents=[doc])
        
        duration = time.time() - start_time
        log_azure_service_call(logger, "Azure AI Search", "upload_documents", 
                             duration, True, None, f"Document ID: {doc_id}")
        log_performance(logger, "document_indexing", duration, 
                       f"Content length: {len(content)} characters")
        
        logger.info(f"✅ AI Search 인덱싱 완료: {doc_id}")
        
    except AzureError as e:
        duration = time.time() - start_time
        log_error_with_context(logger, e, f"Azure AI Search error indexing document: {doc_id}")
        log_azure_service_call(logger, "Azure AI Search", "upload_documents", 
                             duration, False, None, f"Azure Error: {str(e)}")
        logger.error(f"❌ AI Search 인덱싱 실패 (Azure 오류): {doc_id} - {e}")
        raise
        
    except Exception as e:
        duration = time.time() - start_time
        log_error_with_context(logger, e, f"Unexpected error indexing document: {doc_id}")
        log_azure_service_call(logger, "Azure AI Search", "upload_documents", 
                             duration, False, None, f"Unexpected error: {str(e)}")
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
            credential=AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY)
        )
        
        results = search_client.search(query, top=top)
        docs = []
        
        for r in results:
            docs.append({
                "id": r["id"],
                "content": r["content"],
                "metadata": r.get("metadata", {})
            })
        
        duration = time.time() - start_time
        log_azure_service_call(logger, "Azure AI Search", "search", 
                             duration, True, None, f"Query: '{query}', Results: {len(docs)}")
        log_performance(logger, "document_search", duration, 
                       f"Query: '{query}', Results: {len(docs)}")
        
        logger.info(f"✅ AI Search 검색 완료: {len(docs)}개 결과 반환")
        return docs
        
    except AzureError as e:
        duration = time.time() - start_time
        log_error_with_context(logger, e, f"Azure AI Search error searching: {query}")
        log_azure_service_call(logger, "Azure AI Search", "search", 
                             duration, False, None, f"Azure Error: {str(e)}")
        logger.error(f"❌ AI Search 검색 실패 (Azure 오류): {query} - {e}")
        raise
        
    except Exception as e:
        duration = time.time() - start_time
        log_error_with_context(logger, e, f"Unexpected error searching: {query}")
        log_azure_service_call(logger, "Azure AI Search", "search", 
                             duration, False, None, f"Unexpected error: {str(e)}")
        logger.error(f"❌ AI Search 검색 중 예상치 못한 오류: {query} - {e}")
        raise
