from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from services.openai_service import transcribe_audio, summarize_and_extract
from services.blob_service import upload_to_blob
from services.search_service import index_document
from db.cosmos_db import (
    init_cosmos, save_meeting, get_meetings, get_meeting,
    get_action_items, approve_action_item, update_action_item_status
)
import json, os, uuid

# 로깅 시스템 초기화
from config.logging_config import setup_logger, get_logger
setup_logger("api")  # API 전용 로그 설정
logger = get_logger(__name__)

# Cosmos DB 초기화
logger.info("FastAPI 애플리케이션 시작 - Cosmos DB 초기화 중...")
init_cosmos()
logger.info("Cosmos DB 초기화 완료")

app = FastAPI(title="회의록 요약 및 업무 분배 API", 
              description="Azure 기반 회의록 요약 및 업무 분배 AI 에이전트 API")

@app.post("/upload")
async def upload_meeting(file: UploadFile = File(None), text: str = Form(None)):
    """
    회의 파일(음성/문서) 또는 텍스트를 업로드하여 요약 및 액션 아이템을 추출합니다.
    """
    import time
    start_time = time.time()
    
    try:
        # 요청 로깅
        if file:
            logger.log_user_action("api_file_upload", None, {
                "filename": file.filename,
                "content_type": file.content_type,
                "size": getattr(file, 'size', 'unknown')
            })
        else:
            logger.log_user_action("api_text_upload", None, {
                "text_length": len(text) if text else 0
            })
        
        raw_text = None
        file_path = None
        blob_path = None        # 파일 또는 텍스트 처리
        blob_path = None
        if file:
            logger.info(f"파일 처리 시작: {file.filename}")
            file_path = f"/tmp/{file.filename}"
            with open(file_path, "wb") as f_out:
                f_out.write(await file.read())
            
            # 음성 파일 처리
            if file.filename.lower().endswith((".wav", ".mp3")):
                logger.info("음성 파일 전사 시작")
                raw_text = transcribe_audio(file_path)
                blob_path = f"audio/{file.filename}"
            # 텍스트 파일 처리
            else:
                logger.info("텍스트 파일 읽기 시작")
                with open(file_path, "r", encoding="utf-8") as f_in:
                    raw_text = f_in.read()
                blob_path = f"text/{file.filename}"
                
            # Blob 저장소에 업로드 (인덱싱 전에 수행)
            logger.info("Blob Storage 업로드 시작")
            upload_to_blob(file_path, blob_path)
            os.remove(file_path)
            logger.info("파일 처리 및 Blob 업로드 완료")
            
        # 직접 텍스트 입력 처리
        elif text:
            raw_text = text
            logger.info(f"텍스트 직접 입력: {len(text)}자")

        # 입력 검증
        if not raw_text:
            logger.warning("빈 입력 - 파일 또는 텍스트가 없음")
            return {"error": "파일 또는 텍스트를 입력하세요."}

        # 요약 및 액션 아이템 추출
        logger.info("AI 분석 시작")
        result = summarize_and_extract(raw_text)
        
        # Cosmos DB에 먼저 저장 (회의 ID 생성)
        logger.info("Cosmos DB 저장 시작")
        meeting_id = save_meeting(
            meeting_title=result.get("meetingTitle", "제목 없음"), 
            raw_text=raw_text,
            summary_json=result
        )
        
        # Azure Search에 인덱싱 (Blob 업로드 후)
        logger.info("검색 인덱스 등록 시작")
        doc_id = f"meeting_{meeting_id}"
        index_document(doc_id, raw_text, result, blob_path)
        
        duration = time.time() - start_time
        logger.log_performance("api_upload_complete", duration, {
            "meeting_id": meeting_id,
            "action_items_count": len(result.get("actionItems", [])),
            "text_length": len(raw_text)
        })
        
        logger.info(f"✅ API 업로드 완료: {meeting_id} ({duration:.2f}초)")
        return {
            "meeting_id": meeting_id,
            "summary": result.get("summary"),
            "actionItems": result.get("actionItems")
        }
    except Exception as e:
        duration = time.time() - start_time
        logger.log_error_with_context("API upload failed", e, {
            "file_name": getattr(file, 'filename', None) if file else None,
            "text_length": len(text) if text else 0,
            "duration": duration
        })
        logger.error(f"❌ 회의록 업로드 및 처리 오류 ({duration:.2f}초): {e}")
        raise HTTPException(status_code=500, detail=f"회의록 처리 중 오류 발생: {str(e)}")

@app.post("/assign")
async def assign_action_item(meeting_id: str, item_id: str, assignee_id: int, reviewer_name: str = None):
    """
    액션 아이템에 담당자를 할당하고 승인합니다.
    """
    try:
        logger.log_user_action("assign_action_item", None, {
            "meeting_id": meeting_id,
            "item_id": item_id,
            "assignee_id": assignee_id,
            "reviewer_name": reviewer_name
        })
        
        approve_action_item(item_id, meeting_id, assignee_id, reviewer_name)
        logger.info(f"✅ 액션 아이템 할당 완료: {item_id} -> 담당자 {assignee_id}")
        return {"result": "success", "message": "액션 아이템 담당자 할당 및 승인 완료"}
    except Exception as e:
        logger.log_error_with_context("assign action item failed", e, {
            "meeting_id": meeting_id,
            "item_id": item_id,
            "assignee_id": assignee_id
        })
        logger.error(f"❌ 액션 아이템 할당 오류: {e}")
        raise HTTPException(status_code=500, detail=f"액션 아이템 할당 중 오류 발생: {str(e)}")

@app.put("/action-item/{meeting_id}/{item_id}/status")
async def update_item_status(meeting_id: str, item_id: str, status: str):
    """
    액션 아이템의 상태를 업데이트합니다. (미시작, 진행중, 완료, 지연)
    """
    try:
        if status not in ["미시작", "진행중", "완료", "지연"]:
            raise HTTPException(status_code=400, detail="상태는 '미시작', '진행중', '완료', '지연' 중 하나여야 합니다.")
        
        logger.log_user_action("update_action_item_status", None, {
            "meeting_id": meeting_id,
            "item_id": item_id,
            "new_status": status
        })
        
        result = update_action_item_status(item_id, meeting_id, status)
        logger.info(f"✅ 액션 아이템 상태 업데이트 완료: {item_id} -> {status}")
        return {"result": "success", "message": f"액션 아이템 상태가 '{status}'(으)로 업데이트되었습니다."}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.log_error_with_context("update action item status failed", e, {
            "meeting_id": meeting_id,
            "item_id": item_id,
            "status": status
        })
        logger.error(f"❌ 액션 아이템 상태 업데이트 오류: {e}")
        raise HTTPException(status_code=500, detail=f"액션 아이템 상태 업데이트 중 오류 발생: {str(e)}")

@app.get("/meetings")
async def list_meetings():
    """
    모든 회의 목록을 반환합니다.
    """
    try:
        logger.info("회의 목록 조회 요청")
        meetings = get_meetings()
        logger.info(f"✅ 회의 목록 조회 완료: {len(meetings)}개 회의")
        return {"meetings": meetings}
    except Exception as e:
        logger.log_error_with_context("list meetings failed", e, {})
        logger.error(f"❌ 회의 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"회의 목록 조회 중 오류 발생: {str(e)}")

@app.get("/meetings/{meeting_id}")
async def get_meeting_detail(meeting_id: str):
    """
    특정 회의의 상세 정보를 반환합니다.
    """
    try:
        logger.info(f"회의 상세 조회 요청: {meeting_id}")
        meeting = get_meeting(meeting_id)
        if not meeting:
            logger.warning(f"회의 찾을 수 없음: {meeting_id}")
            raise HTTPException(status_code=404, detail=f"ID가 '{meeting_id}'인 회의를 찾을 수 없습니다.")
            
        action_items = get_action_items(meeting_id)
        logger.info(f"✅ 회의 상세 조회 완료: {meeting_id}, 액션 아이템 {len(action_items)}개")
        return {
            "meeting": meeting,
            "actionItems": action_items
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.log_error_with_context("get meeting detail failed", e, {
            "meeting_id": meeting_id
        })
        logger.error(f"❌ 회의 상세 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"회의 상세 조회 중 오류 발생: {str(e)}")

@app.get("/dashboard")
async def dashboard():
    """
    대시보드를 위한 통계 정보를 반환합니다.
    """
    try:
        logger.info("대시보드 정보 조회 요청")
        meetings = get_meetings()
        
        # 통계 정보 생성
        total_meetings = len(meetings)
        action_items_by_status = {"미시작": 0, "진행중": 0, "완료": 0, "지연": 0}
        action_items_by_assignee = {}
        
        for meeting in meetings:
            meeting_id = meeting["id"]
            items = get_action_items(meeting_id)
            
            for item in items:
                # 상태별 통계
                status = item.get("status", "미시작")
                action_items_by_status[status] = action_items_by_status.get(status, 0) + 1
                
                # 담당자별 통계
                assignee_id = item.get("finalAssigneeId") or item.get("recommendedAssigneeId")
                if assignee_id:
                    assignee_id = str(assignee_id)
                    action_items_by_assignee[assignee_id] = action_items_by_assignee.get(assignee_id, 0) + 1
        
        logger.info(f"✅ 대시보드 정보 조회 완료: 회의 {total_meetings}개")
        return {
            "total_meetings": total_meetings,
            "action_items_by_status": action_items_by_status,
            "action_items_by_assignee": action_items_by_assignee,
            "recent_meetings": meetings[:5]  # 최근 5개 회의만 반환
        }
    except Exception as e:
        logger.log_error_with_context("get dashboard info failed", e, {})
        logger.error(f"❌ 대시보드 정보 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"대시보드 정보 조회 중 오류 발생: {str(e)}")