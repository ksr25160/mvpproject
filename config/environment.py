"""
환경 설정 관리 모듈
로컬 개발 환경과 Azure 클라우드 환경을 자동으로 감지하고 적절한 설정을 적용
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional
from enum import Enum

class Environment(Enum):
    """환경 유형"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    AZURE = "azure"

class Config:
    """환경별 설정 관리 클래스"""
    
    def __init__(self):
        self.environment = self._detect_environment()
        self.settings = self._load_settings()
    
    def _detect_environment(self) -> Environment:
        """현재 실행 환경 감지"""
        # Azure App Service 환경 감지
        if os.getenv("WEBSITE_SITE_NAME") or os.getenv("APPSETTING_WEBSITE_SITE_NAME"):
            return Environment.AZURE
        
        # 개발 환경 확인
        if os.getenv("ENVIRONMENT") == "development" or os.path.exists(".env"):
            return Environment.DEVELOPMENT
        
        # 기본적으로 프로덕션 환경으로 간주
        return Environment.PRODUCTION
    
    def _load_settings(self) -> Dict[str, Any]:
        """환경별 설정 로드"""
        base_settings = {
            # 공통 설정
            "app_name": "Meeting AI Assistant",
            "version": "1.0.0",
            
            # 로그 설정
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file_encoding": "utf-8",
                "max_file_size_mb": 10,
                "backup_count": 5
            },
            
            # Streamlit 설정
            "streamlit": {
                "page_title": "Meeting AI Assistant",
                "page_icon": "🤖",
                "layout": "wide",
                "initial_sidebar_state": "expanded"
            }
        }
        
        if self.environment == Environment.DEVELOPMENT:
            return {**base_settings, **self._get_development_settings()}
        elif self.environment == Environment.AZURE:
            return {**base_settings, **self._get_azure_settings()}
        else:
            return {**base_settings, **self._get_production_settings()}
    
    def _get_development_settings(self) -> Dict[str, Any]:
        """개발 환경 설정"""
        return {
            "debug": True,
            "logging": {
                "level": "DEBUG",
                "console_output": True,
                "file_output": True,
                "structured_output": True
            },
            
            "azure_services": {
                "use_local_auth": True,
                "connection_timeout": 30,
                "retry_attempts": 3,
                "mock_services": False  # 개발 중 Azure 서비스 모킹 여부
            },
            
            "streamlit": {
                "server_port": 8501,
                "server_address": "localhost",
                "auto_rerun": True
            },
            
            "file_upload": {
                "max_size_mb": 50,
                "allowed_extensions": [".pdf", ".docx", ".txt", ".wav", ".mp3", ".m4a"],
                "temp_dir": "temp"
            }
        }
    
    def _get_azure_settings(self) -> Dict[str, Any]:
        """Azure 환경 설정"""
        return {
            "debug": False,
            "logging": {
                "level": "INFO",
                "console_output": False,
                "file_output": True,
                "structured_output": True,
                "azure_monitor": True  # Azure Monitor/Application Insights 통합
            },
            
            "azure_services": {
                "use_managed_identity": True,
                "connection_timeout": 60,
                "retry_attempts": 5,
                "enable_metrics": True
            },
            
            "streamlit": {
                "server_port": int(os.getenv("WEBSITE_PORT", "8501")),
                "server_address": "0.0.0.0",
                "auto_rerun": False
            },
            
            "file_upload": {
                "max_size_mb": 100,
                "allowed_extensions": [".pdf", ".docx", ".txt", ".wav", ".mp3", ".m4a"],
                "temp_dir": "/tmp"
            },
            
            "security": {
                "enable_cors": True,
                "allowed_origins": ["*"],  # Azure에서는 더 제한적으로 설정
                "enable_https_redirect": True
            }
        }
    
    def _get_production_settings(self) -> Dict[str, Any]:
        """프로덕션 환경 설정"""
        return {
            "debug": False,
            "logging": {
                "level": "WARNING",
                "console_output": False,
                "file_output": True,
                "structured_output": True
            },
            
            "azure_services": {
                "use_managed_identity": True,
                "connection_timeout": 60,
                "retry_attempts": 5,
                "enable_metrics": True
            },
            
            "streamlit": {
                "server_port": 8501,
                "server_address": "0.0.0.0",
                "auto_rerun": False
            },
            
            "file_upload": {
                "max_size_mb": 100,
                "allowed_extensions": [".pdf", ".docx", ".txt", ".wav", ".mp3", ".m4a"],
                "temp_dir": "/tmp"
            },
            
            "security": {
                "enable_cors": True,
                "allowed_origins": [],  # 프로덕션에서는 특정 도메인만 허용
                "enable_https_redirect": True
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """설정 값 조회"""
        keys = key.split('.')
        value = self.settings
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def is_azure(self) -> bool:
        """Azure 환경 여부 확인"""
        return self.environment == Environment.AZURE
    
    def is_development(self) -> bool:
        """개발 환경 여부 확인"""
        return self.environment == Environment.DEVELOPMENT
    
    def is_production(self) -> bool:
        """프로덕션 환경 여부 확인"""
        return self.environment == Environment.PRODUCTION
    
    def get_log_directory(self) -> Path:
        """로그 디렉토리 경로 반환"""
        if self.is_azure():
            # Azure App Service에서는 /home/LogFiles 사용
            log_dir = Path("/home/LogFiles")
            if not log_dir.exists():
                # 권한이 없다면 현재 디렉토리 사용
                log_dir = Path("logs")
        else:
            log_dir = Path("logs")
        
        log_dir.mkdir(exist_ok=True)
        return log_dir
    
    def get_temp_directory(self) -> Path:
        """임시 디렉토리 경로 반환"""
        temp_dir_path = self.get("file_upload.temp_dir", "temp")
        temp_dir = Path(temp_dir_path)
        temp_dir.mkdir(exist_ok=True)
        return temp_dir
    
    def get_azure_credentials(self) -> Dict[str, Optional[str]]:
        """Azure 서비스 연결 정보 반환"""
        if self.is_azure():
            # Azure 환경에서는 환경변수에서 직접 읽기
            return {
                "cosmos_endpoint": os.getenv("COSMOS_ENDPOINT"),
                "cosmos_key": os.getenv("COSMOS_KEY"),
                "storage_connection_string": os.getenv("AZURE_BLOB_CONNECTION_STRING"),
                "search_endpoint": os.getenv("AZURE_SEARCH_ENDPOINT"),
                "search_key": os.getenv("AZURE_SEARCH_ADMIN_KEY"),
                "openai_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
                "openai_key": os.getenv("AZURE_OPENAI_KEY"),
                "speech_key": os.getenv("AZURE_SPEECH_KEY"),
                "speech_region": os.getenv("AZURE_SPEECH_REGION")
            }
        else:
            # 로컬 환경에서는 .env 파일 또는 환경변수 사용
            from dotenv import load_dotenv
            load_dotenv()
            
            return {
                "cosmos_endpoint": os.getenv("COSMOS_ENDPOINT"),
                "cosmos_key": os.getenv("COSMOS_KEY"),
                "storage_connection_string": os.getenv("AZURE_BLOB_CONNECTION_STRING"),
                "search_endpoint": os.getenv("AZURE_SEARCH_ENDPOINT"),
                "search_key": os.getenv("AZURE_SEARCH_ADMIN_KEY"),
                "openai_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
                "openai_key": os.getenv("AZURE_OPENAI_KEY"),
                "speech_key": os.getenv("AZURE_SPEECH_KEY"),
                "speech_region": os.getenv("AZURE_SPEECH_REGION")
            }

# 전역 설정 인스턴스
config = Config()

def get_config() -> Config:
    """전역 설정 인스턴스 반환"""
    return config
