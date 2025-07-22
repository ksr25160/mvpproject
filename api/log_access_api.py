"""
로그 접근 API - Azure Web App 배포 후 로그 파일에 접근하기 위한 FastAPI 엔드포인트
"""
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, FileResponse
from config.logging_config import get_logger

app = FastAPI(
    title="Meeting AI - Log Access API",
    description="로그 파일 접근을 위한 API",
    version="1.0.0"
)

security = HTTPBearer()
logger = get_logger(__name__)

# 간단한 토큰 기반 인증 (실제 환경에서는 더 강력한 인증 시스템 사용)
ADMIN_TOKEN = os.getenv("LOG_ACCESS_TOKEN", "meeting-ai-log-access-2024")

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """토큰 검증"""
    if credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    return credentials.credentials

@app.get("/")
async def root():
    """API 상태 확인"""
    return {
        "service": "Meeting AI Log Access API",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/logs/list")
async def list_log_files(token: str = Security(verify_token)):
    """사용 가능한 로그 파일 목록 조회"""
    try:
        logs_dir = Path("logs")
        if not logs_dir.exists():
            return {"log_files": [], "message": "Logs directory not found"}
        
        log_files = []
        for file_path in logs_dir.glob("*.log"):
            stat = file_path.stat()
            log_files.append({
                "filename": file_path.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "type": "general" if "error" not in file_path.name else "error"
            })
        
        # JSON 로그 파일들
        for file_path in logs_dir.glob("*_structured.json"):
            stat = file_path.stat()
            log_files.append({
                "filename": file_path.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "type": "structured"
            })
        
        return {
            "log_files": sorted(log_files, key=lambda x: x["modified"], reverse=True),
            "total_files": len(log_files)
        }
        
    except Exception as e:
        logger.error(f"Error listing log files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing log files: {str(e)}")

@app.get("/logs/download/{filename}")
async def download_log_file(filename: str, token: str = Security(verify_token)):
    """로그 파일 다운로드"""
    try:
        file_path = Path("logs") / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Log file not found")
        
        # 보안: 상위 디렉토리 접근 방지
        if not file_path.resolve().is_relative_to(Path("logs").resolve()):
            raise HTTPException(status_code=403, detail="Access denied")
        
        logger.log_security_event("log_file_downloaded", {
            "filename": filename,
            "file_size": file_path.stat().st_size
        })
        
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type='application/octet-stream'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading log file {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading log file: {str(e)}")

@app.get("/logs/tail/{filename}")
async def tail_log_file(
    filename: str,
    lines: int = Query(default=100, ge=1, le=1000, description="Number of lines to read from end of file"),
    token: str = Security(verify_token)
):
    """로그 파일의 마지막 N줄 조회"""
    try:
        file_path = Path("logs") / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Log file not found")
        
        # 보안: 상위 디렉토리 접근 방지
        if not file_path.resolve().is_relative_to(Path("logs").resolve()):
            raise HTTPException(status_code=403, detail="Access denied")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            tail_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return {
            "filename": filename,
            "total_lines": len(all_lines),
            "returned_lines": len(tail_lines),
            "lines": [line.rstrip('\n') for line in tail_lines]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading log file {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")

@app.get("/logs/search/{filename}")
async def search_log_file(
    filename: str,
    query: str = Query(..., description="Search term"),
    max_results: int = Query(default=50, ge=1, le=500, description="Maximum number of results"),
    token: str = Security(verify_token)
):
    """로그 파일에서 검색"""
    try:
        file_path = Path("logs") / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Log file not found")
        
        # 보안: 상위 디렉토리 접근 방지
        if not file_path.resolve().is_relative_to(Path("logs").resolve()):
            raise HTTPException(status_code=403, detail="Access denied")
        
        results = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if query.lower() in line.lower():
                    results.append({
                        "line_number": line_num,
                        "content": line.rstrip('\n')
                    })
                    if len(results) >= max_results:
                        break
        
        return {
            "filename": filename,
            "query": query,
            "results_count": len(results),
            "max_results": max_results,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching log file {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching log file: {str(e)}")

@app.get("/logs/structured/recent")
async def get_recent_structured_logs(
    hours: int = Query(default=24, ge=1, le=168, description="Hours to look back"),
    level: Optional[str] = Query(default=None, description="Log level filter (ERROR, WARNING, INFO)"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records"),
    token: str = Security(verify_token)
):
    """최근 구조화된 로그 조회"""
    try:
        logs_dir = Path("logs")
        cutoff_time = datetime.now() - timedelta(hours=hours)
        structured_logs = []
        
        # 구조화된 JSON 로그 파일들 처리
        for file_path in logs_dir.glob("*_structured.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            log_entry = json.loads(line.strip())
                            
                            # 시간 필터링
                            log_time = datetime.fromisoformat(log_entry.get('timestamp', ''))
                            if log_time < cutoff_time:
                                continue
                            
                            # 로그 레벨 필터링
                            if level and log_entry.get('level', '').upper() != level.upper():
                                continue
                            
                            structured_logs.append(log_entry)
                            
                        except (json.JSONDecodeError, ValueError):
                            continue
                            
            except Exception as e:
                logger.error(f"Error processing structured log file {file_path}: {str(e)}")
                continue
        
        # 시간순 정렬 및 제한
        structured_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        structured_logs = structured_logs[:limit]
        
        return {
            "hours_back": hours,
            "level_filter": level,
            "total_records": len(structured_logs),
            "records": structured_logs
        }
        
    except Exception as e:
        logger.error(f"Error retrieving structured logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving structured logs: {str(e)}")

@app.get("/logs/stats")
async def get_log_statistics(
    hours: int = Query(default=24, ge=1, le=168, description="Hours to analyze"),
    token: str = Security(verify_token)
):
    """로그 통계 정보 조회"""
    try:
        logs_dir = Path("logs")
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        stats = {
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "performance_issues": 0,
            "security_events": 0,
            "azure_service_calls": 0,
            "unique_sessions": set(),
            "file_sizes": {}
        }
        
        # 로그 파일 크기 정보
        for file_path in logs_dir.glob("*.log"):
            stats["file_sizes"][file_path.name] = file_path.stat().st_size
        
        for file_path in logs_dir.glob("*_structured.json"):
            stats["file_sizes"][file_path.name] = file_path.stat().st_size
        
        # 구조화된 로그 분석
        for file_path in logs_dir.glob("*_structured.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            log_entry = json.loads(line.strip())
                            
                            # 시간 필터링
                            log_time = datetime.fromisoformat(log_entry.get('timestamp', ''))
                            if log_time < cutoff_time:
                                continue
                            
                            # 통계 집계
                            level = log_entry.get('level', '').upper()
                            if level == 'ERROR':
                                stats["error_count"] += 1
                            elif level == 'WARNING':
                                stats["warning_count"] += 1
                            elif level == 'INFO':
                                stats["info_count"] += 1
                            
                            # 특별한 이벤트 유형 카운트
                            event_type = log_entry.get('event_type', '')
                            if event_type == 'performance_metric':
                                if log_entry.get('data', {}).get('duration', 0) > 5.0:  # 5초 이상
                                    stats["performance_issues"] += 1
                            elif event_type == 'security_event':
                                stats["security_events"] += 1
                            elif event_type == 'azure_service_call':
                                stats["azure_service_calls"] += 1
                            
                            # 세션 수집
                            session_id = log_entry.get('session_id')
                            if session_id:
                                stats["unique_sessions"].add(session_id)
                                
                        except (json.JSONDecodeError, ValueError):
                            continue
                            
            except Exception as e:
                logger.error(f"Error processing structured log file {file_path}: {str(e)}")
                continue
        
        # set을 int로 변환
        stats["unique_sessions"] = len(stats["unique_sessions"])
        
        return {
            "analysis_period_hours": hours,
            "statistics": stats,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating log statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating log statistics: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8502)
