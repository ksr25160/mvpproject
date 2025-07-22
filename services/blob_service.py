from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import AzureError
import os
import time
import logging
from config.logging_config import log_error_with_context, log_performance, log_azure_service_call

# 로깅 설정
logger = logging.getLogger("blob_service")

def upload_to_blob(file_path, blob_name):
    """파일을 Azure Blob Storage에 업로드합니다."""
    start_time = time.time()
    try:
        from config.config import AZURE_BLOB_CONNECTION_STRING, AZURE_BLOB_CONTAINER
        
        logger.info(f"Blob 업로드 시작: {blob_name}")
        
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_BLOB_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(AZURE_BLOB_CONTAINER)
        
        # 파일 크기 확인
        file_size = os.path.getsize(file_path)
        
        with open(file_path, "rb") as data:
            container_client.upload_blob(name=blob_name, data=data, overwrite=True)
        
        duration = time.time() - start_time
        
        log_azure_service_call(logger, "Azure Blob Storage", "upload_blob", 
                             duration, True, None, f"File: {blob_name}, Size: {file_size} bytes")
        log_performance(logger, "blob_upload", duration, f"File size: {file_size} bytes")
        
        logger.info(f"✅ Blob 업로드 완료: {blob_name}")
        
    except AzureError as e:
        duration = time.time() - start_time
        log_error_with_context(logger, e, f"Azure Blob Storage error for file: {blob_name}")
        log_azure_service_call(logger, "Azure Blob Storage", "upload_blob", 
                             duration, False, None, f"Azure Error: {str(e)}")
        logger.error(f"❌ Blob 업로드 실패 (Azure 오류): {blob_name} - {e}")
        raise
        
    except FileNotFoundError as e:
        duration = time.time() - start_time
        log_error_with_context(logger, e, f"File not found: {file_path}")
        logger.error(f"❌ 파일을 찾을 수 없습니다: {file_path}")
        raise
        
    except Exception as e:
        duration = time.time() - start_time
        log_error_with_context(logger, e, f"Unexpected error uploading {blob_name}")
        log_azure_service_call(logger, "Azure Blob Storage", "upload_blob", 
                             duration, False, None, f"Unexpected error: {str(e)}")
        logger.error(f"❌ Blob 업로드 중 예상치 못한 오류: {blob_name} - {e}")
        raise