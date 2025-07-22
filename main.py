"""
Azure Web App 배포를 위한 메인 애플리케이션 엔트리포인트
"""
import os
import sys
from pathlib import Path

# 현재 디렉토리를 Python 경로에 추가
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 환경 설정 초기화
from config.environment import config
from config.logging_config import setup_logger, get_logger

# 로깅 설정 초기화
setup_logger()
logger = get_logger(__name__)

logger.info(f"Starting Meeting AI Application in {config.environment.value} environment")
logger.info(f"Python version: {sys.version}")
logger.info(f"Python path: {sys.path}")
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"Available environment variables: PORT={os.getenv('PORT')}, WEBSITES_PORT={os.getenv('WEBSITES_PORT')}, WEBSITE_PORT={os.getenv('WEBSITE_PORT')}")
logger.info(f"Directory contents: {os.listdir('.')}")

def main():
    """메인 애플리케이션 실행"""
    try:
        # Azure 환경에서는 로그 API도 함께 실행
        if config.is_azure():
            import threading
            from api.log_access_api import app as log_api
            import uvicorn
            
            # 로그 API를 백그라운드에서 실행
            def run_log_api():
                uvicorn.run(log_api, host="0.0.0.0", port=8502, log_level="warning")
            
            log_api_thread = threading.Thread(target=run_log_api, daemon=True)
            log_api_thread.start()
            logger.info("Log Access API started on port 8502")
        
        # Streamlit 애플리케이션 실행
        logger.info("Starting Streamlit application...")
        
        # Streamlit 설정
        streamlit_config = config.get("streamlit", {})
        port = streamlit_config.get("server_port", 8501)
        address = streamlit_config.get("server_address", "0.0.0.0")
          # Azure App Service에서는 환경변수에서 포트를 가져옴
        if config.is_azure():
            port = int(os.getenv("PORT", os.getenv("WEBSITES_PORT", os.getenv("WEBSITE_PORT", "8000"))))
        
        logger.info(f"Starting Streamlit on {address}:{port}")
        
        # Streamlit 애플리케이션 실행
        import subprocess
        cmd = [
            sys.executable, "-m", "streamlit", "run", 
            str(current_dir / "app" / "app.py"),
            "--server.port", str(port),
            "--server.address", address,
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--theme.base", "light"
        ]
        
        logger.info(f"Executing command: {' '.join(cmd)}")
        subprocess.run(cmd)
        
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
