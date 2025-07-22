import logging
import os
import traceback
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import json

# 환경 설정 통합
def get_environment_config():
    """환경 설정을 가져옵니다 (순환 import 방지)"""
    try:
        from config.environment import get_config
        return get_config()
    except ImportError:
        return None

def get_logger(name: str = None) -> logging.Logger:
    """로거 인스턴스를 반환합니다."""
    if name is None:
        name = __name__
    
    logger = logging.getLogger(name)
    
    # 로거가 아직 설정되지 않았다면 기본 설정 적용
    if not logger.handlers:
        setup_logger()
      # 커스텀 메서드 추가 (전역 함수 참조)
    def custom_log_error_with_context(message: str, error: Exception = None, context: Dict[str, Any] = None):
        return log_error_with_context(logger, error, context)
    
    def custom_log_user_action(action: str, user_id: str = None, details: Dict[str, Any] = None):
        return log_user_action(logger, action, user_id, None, details)
    
    def custom_log_performance(operation: str, duration: float, details: Dict[str, Any] = None):
        return log_performance(logger, operation, duration, details)
    
    def custom_log_security_event(event_type: str, details: Dict[str, Any] = None):
        return log_security_event(logger, event_type, str(details) if details else "", severity='INFO')
    
    def custom_log_azure_service_call(service: str, operation: str, duration: float = None, 
                                    response_code: int = None, additional_info: Dict[str, Any] = None):
        success = response_code is None or (200 <= response_code < 300)
        return log_azure_service_call(logger, service, operation, duration, success, response_code, additional_info)
    
    def custom_log_business_event(event_name: str, user_id: str = None, meeting_id: str = None, details: str = None):
        return log_business_event(logger, event_name, details, user_id, meeting_id)
    
    # 메서드를 로거에 바인딩
    logger.log_error_with_context = custom_log_error_with_context
    logger.log_user_action = custom_log_user_action
    logger.log_performance = custom_log_performance
    logger.log_security_event = custom_log_security_event
    logger.log_azure_service_call = custom_log_azure_service_call
    logger.log_business_event = custom_log_business_event
    
    return logger

class CustomJsonFormatter(logging.Formatter):
    """구조화된 JSON 로깅을 위한 커스텀 포매터"""
    
    def format(self, record):
        # 기본 로그 정보
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
        }
        
        # 예외 정보가 있다면 추가
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # 사용자 정의 필드 추가
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                log_entry[key] = value
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)

def setup_logger(app_name: str = "mvp_meeting_ai"):
    """향상된 로깅 시스템을 설정합니다."""
    
    # 환경 설정 가져오기
    env_config = get_environment_config()
    
    # 로그 디렉토리 생성 (환경별 경로 사용)
    if env_config:
        log_dir = env_config.get_log_directory()
        log_level = getattr(logging, env_config.get("logging.level", "INFO"))
        console_output = env_config.get("logging.console_output", True)
        file_output = env_config.get("logging.file_output", True)
        structured_output = env_config.get("logging.structured_output", True)
    else:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_level = logging.INFO
        console_output = True
        file_output = True
        structured_output = True
    
    # 로그 파일명 설정 (날짜별)
    today = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"{app_name}_{today}.log"
    error_log_file = log_dir / f"{app_name}_error_{today}.log"
    json_log_file = log_dir / f"{app_name}_structured_{today}.jsonl"
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 기존 핸들러 제거 (중복 방지)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 포매터 설정
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    json_formatter = CustomJsonFormatter()
    
    # 1. 콘솔 핸들러 (INFO 이상, 개발 환경에서만)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # 2. 일반 로그 파일 핸들러 (INFO 이상)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # 3. 에러 로그 파일 핸들러 (ERROR 이상만)
    error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)
    
    # 4. 구조화된 JSON 로그 핸들러 (WARNING 이상)
    json_handler = logging.FileHandler(json_log_file, encoding='utf-8')
    json_handler.setLevel(logging.WARNING)
    json_handler.setFormatter(json_formatter)
    root_logger.addHandler(json_handler)
    
    logger = logging.getLogger(app_name)
    logger.info(f"로깅 시스템 초기화 완료 - 로그 파일: {log_file}")
    
    return logger

def log_error_with_context(logger, error, context_info=None, user_id=None, session_id=None):
    """에러를 상세한 컨텍스트 정보와 함께 로깅합니다."""
    error_msg = f"ERROR OCCURRED: {str(error)}"
    
    # 추가 컨텍스트 정보를 로그 레코드에 포함
    extra = {
        'error_type': type(error).__name__,
        'context': context_info,
        'user_id': user_id,
        'session_id': session_id,
        'stack_trace': traceback.format_exc() if sys.exc_info()[0] else None
    }
    
    if context_info:
        error_msg += f"\nContext: {context_info}"
    
    # 스택 트레이스 포함하여 ERROR 레벨로 로깅
    logger.error(error_msg, exc_info=True, extra=extra)

def log_user_action(logger, action, user_id=None, session_id=None, additional_data=None):
    """사용자 액션을 로깅합니다."""
    msg = f"USER ACTION: {action}"
    
    extra = {
        'action_type': 'user_action',
        'user_id': user_id,
        'session_id': session_id,
        'additional_data': additional_data
    }
    
    if user_id:
        msg += f" | User: {user_id}"
    
    if additional_data:
        msg += f" | Data: {additional_data}"
    
    logger.info(msg, extra=extra)

def log_performance(logger, operation_name, duration, additional_info=None, user_id=None):
    """성능 관련 정보를 로깅합니다."""
    msg = f"PERFORMANCE: {operation_name} took {duration:.2f}s"
    
    extra = {
        'metric_type': 'performance',
        'operation': operation_name,
        'duration_seconds': duration,
        'user_id': user_id,
        'additional_info': additional_info
    }
    
    if additional_info:
        msg += f" | Info: {additional_info}"
    
    # 성능이 3초 이상이면 WARNING으로, 아니면 INFO로 로깅
    if duration > 3.0:
        logger.warning(msg, extra=extra)
    else:
        logger.info(msg, extra=extra)

def log_security_event(logger, event_type, description, user_id=None, ip_address=None, severity='INFO'):
    """보안 관련 이벤트를 로깅합니다."""
    msg = f"SECURITY EVENT: {event_type} - {description}"
    
    extra = {
        'event_type': 'security',
        'security_event_type': event_type,
        'user_id': user_id,
        'ip_address': ip_address,
        'severity': severity
    }
    
    # 심각도에 따른 로그 레벨 설정
    if severity.upper() == 'CRITICAL':
        logger.critical(msg, extra=extra)
    elif severity.upper() == 'HIGH':
        logger.error(msg, extra=extra)
    elif severity.upper() == 'MEDIUM':
        logger.warning(msg, extra=extra)
    else:
        logger.info(msg, extra=extra)

def log_azure_service_call(logger, service_name, operation, duration=None, success=True, 
                          response_code=None, additional_info=None):
    """Azure 서비스 호출을 로깅합니다."""
    status = "SUCCESS" if success else "FAILED"
    msg = f"AZURE SERVICE: {service_name}.{operation} - {status}"
    
    extra = {
        'service_type': 'azure_service',
        'service_name': service_name,
        'operation': operation,
        'success': success,
        'response_code': response_code,
        'duration_seconds': duration,
        'additional_info': additional_info
    }
    
    if duration:
        msg += f" ({duration:.2f}s)"
    
    if response_code:
        msg += f" - HTTP {response_code}"
    
    # 실패한 경우 ERROR로, 성공한 경우 INFO로 로깅
    if not success:
        logger.error(msg, extra=extra)
    else:
        logger.info(msg, extra=extra)

def log_business_event(logger, event_name, details=None, user_id=None, meeting_id=None):
    """비즈니스 로직 이벤트를 로깅합니다."""
    msg = f"BUSINESS EVENT: {event_name}"
    
    extra = {
        'event_type': 'business',
        'event_name': event_name,
        'user_id': user_id,
        'meeting_id': meeting_id,
        'details': details
    }
    
    if details:
        msg += f" - {details}"
    
    logger.info(msg, extra=extra)
