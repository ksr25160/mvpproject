from azure.cosmos import CosmosClient, PartitionKey, exceptions
import config.config as config
from datetime import datetime
import json
import uuid
import logging
import time
from config.logging_config import log_error_with_context, log_performance, log_azure_service_call, log_business_event

# 로깅 설정
logger = logging.getLogger("cosmos_db")

def get_client():
    """Cosmos DB 클라이언트를 반환합니다."""
    try:
        client = CosmosClient(config.COSMOS_ENDPOINT, config.COSMOS_KEY)
        log_azure_service_call(logger, "Azure Cosmos DB", "create_client", None, True)
        return client
    except Exception as e:
        log_error_with_context(logger, e, "Failed to create Cosmos DB client")
        log_azure_service_call(logger, "Azure Cosmos DB", "create_client", None, False, None, str(e))
        logger.error(f"Cosmos DB 클라이언트 생성 실패: {e}")
        raise

def init_cosmos():
    """Cosmos DB 및 필요한 컨테이너를 초기화합니다."""
    start_time = time.time()
    try:
        client = get_client()
        
        # 데이터베이스 생성 (없는 경우)
        try:
            db = client.create_database(config.COSMOS_DB_NAME)
            log_business_event(logger, "database_created", f"Database '{config.COSMOS_DB_NAME}' created")
            logger.info(f"Cosmos DB '{config.COSMOS_DB_NAME}' 생성됨")
        except exceptions.CosmosResourceExistsError:
            db = client.get_database_client(config.COSMOS_DB_NAME)
            logger.info(f"Cosmos DB '{config.COSMOS_DB_NAME}' 이미 존재함")        # 필요한 컨테이너 생성 (없는 경우)
        containers = [
            (config.COSMOS_MEETINGS_CONTAINER, "/id"),
            (config.COSMOS_ACTION_ITEMS_CONTAINER, "/meetingId"),
            (config.COSMOS_HISTORY_CONTAINER, "/actionItemId"),
            (config.COSMOS_AUDIT_CONTAINER, "/resourceId"),
            (config.COSMOS_STAFF_CONTAINER, "/id"),
            (config.COSMOS_CHAT_HISTORY_CONTAINER, "/session_id")
        ]
        
        created_containers = []
        existing_containers = []
        
        for container_name, partition_key in containers:
            try:
                # 먼저 컨테이너 존재 여부 확인
                container_client = db.get_container_client(container_name)
                container_client.read()  # 컨테이너가 존재하는지 확인
                existing_containers.append(container_name)
            except exceptions.CosmosResourceNotFoundError:
                # 컨테이너가 없으면 생성
                try:
                    db.create_container(id=container_name, partition_key=PartitionKey(path=partition_key))
                    created_containers.append(container_name)
                    logger.info(f"컨테이너 '{container_name}' 생성됨")
                except exceptions.CosmosResourceExistsError:
                    # 동시 생성으로 인한 경합 상황 처리
                    existing_containers.append(container_name)
            except Exception as e:
                logger.warning(f"컨테이너 '{container_name}' 상태 확인 실패: {e}")
        
        duration = time.time() - start_time
        
        # 로그 메시지 개선: 이미 존재하는 컨테이너에 대한 정보 제공
        if existing_containers and not created_containers:
            logger.info(f"모든 컨테이너가 이미 존재함: {', '.join(existing_containers)}")
        elif existing_containers and created_containers:
            logger.info(f"기존 컨테이너: {', '.join(existing_containers)}, 새로 생성된 컨테이너: {', '.join(created_containers)}")
        elif created_containers:
            logger.info(f"새로 생성된 컨테이너: {', '.join(created_containers)}")
        
        log_performance(logger, "cosmos_db_initialization", duration,
                       f"Created: {len(created_containers)}, Existing: {len(existing_containers)}")
        
        if created_containers:
            log_business_event(logger, "containers_initialized", 
                             f"Created containers: {', '.join(created_containers)}")
        else:
            log_business_event(logger, "containers_verified", 
                             f"All containers already exist: {', '.join(existing_containers)}")
        
        return True
        
    except Exception as e:
        duration = time.time() - start_time
        log_error_with_context(logger, e, "Cosmos DB initialization failed")
        log_azure_service_call(logger, "Azure Cosmos DB", "initialization", 
                             duration, False, None, str(e))
        logger.error(f"Cosmos DB 초기화 실패: {e}")
        return False

def save_meeting(meeting_title, raw_text, summary_json):
    """회의 정보를 저장합니다."""
    start_time = time.time()
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_MEETINGS_CONTAINER)
        
        meeting_id = f"meeting_{uuid.uuid4().hex[:8]}"
        created_at = datetime.utcnow().isoformat()
        
        # summary_json이 문자열인 경우 파싱
        if isinstance(summary_json, str):
            try:
                summary_dict = json.loads(summary_json)
            except (json.JSONDecodeError, TypeError):
                summary_dict = {"error": "Failed to parse summary", "raw": summary_json}
        else:
            summary_dict = summary_json
        
        meeting_item = {
            "id": meeting_id,
            "title": meeting_title,
            "raw_text": raw_text,
            "summary": summary_json,  # 원본 저장
            "created_at": created_at,
            "type": "meeting"
        }
        
        container.create_item(body=meeting_item)
        
        # 액션 아이템 저장 (딕셔너리 버전 사용)
        action_items_count = 0
        if "actionItems" in summary_dict:
            save_action_items(meeting_id, summary_dict["actionItems"])
            action_items_count = len(summary_dict["actionItems"])
        
        duration = time.time() - start_time
        log_azure_service_call(logger, "Azure Cosmos DB", "create_meeting", 
                             duration, True, None, f"Meeting ID: {meeting_id}")
        log_performance(logger, "save_meeting", duration, 
                       f"Meeting: {meeting_id}, Actions: {action_items_count}")
        log_business_event(logger, "meeting_saved", 
                         f"Meeting '{meeting_title}' saved with {action_items_count} action items", 
                         meeting_id=meeting_id)
            
        return meeting_id
        
    except exceptions.CosmosHttpResponseError as e:
        duration = time.time() - start_time
        log_error_with_context(logger, e, f"Cosmos DB HTTP error saving meeting: {meeting_title}")
        log_azure_service_call(logger, "Azure Cosmos DB", "create_meeting", 
                             duration, False, e.status_code, str(e))
        logger.error(f"회의 저장 실패 (HTTP {e.status_code}): {e}")
        raise
        
    except Exception as e:
        duration = time.time() - start_time
        log_error_with_context(logger, e, f"Failed to save meeting: {meeting_title}")
        log_azure_service_call(logger, "Azure Cosmos DB", "create_meeting", 
                             duration, False, None, str(e))
        logger.error(f"회의 저장 실패: {e}")
        raise

def save_action_items(meeting_id, action_items):
    """액션 아이템을 저장합니다."""
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_ACTION_ITEMS_CONTAINER)
        
        for idx, item in enumerate(action_items):
            item_id = f"item_{meeting_id}_{idx}"
            
            # 담당자 추천 (인사정보가 있는 경우)
            recommended_assignee = None
            recommended_assignee_name = item.get("recommendedAssigneeId", item.get("assignee", ""))
            
            # 액션 아이템 설명을 기반으로 담당자 추천
            description = item.get("description", "")
            if description:
                try:
                    recommended_staff = recommend_assignee_for_task(description)
                    if recommended_staff:
                        recommended_assignee = recommended_staff.get('name', '')
                        recommended_assignee_name = recommended_staff.get('name', recommended_assignee_name)
                except Exception as e:
                    logger.warning(f"담당자 추천 실패: {e}")
            
            action_item = {
                "id": item_id,
                "meetingId": meeting_id,
                "description": description,
                "recommendedAssigneeId": recommended_assignee_name,
                "dueDate": item.get("dueDate", ""),
                "finalAssigneeId": None,
                "approved": False,
                "status": "미시작",
                "created_at": datetime.utcnow().isoformat()
            }
            
            container.create_item(body=action_item)
        
    except Exception as e:
        logger.error(f"액션 아이템 저장 실패: {e}")
        raise

def get_meetings(top=100):
    """모든 회의 목록을 조회합니다."""
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_MEETINGS_CONTAINER)
        
        query = "SELECT * FROM c WHERE c.type = 'meeting' ORDER BY c.created_at DESC"
        items = list(container.query_items(
            query=query,
            enable_cross_partition_query=True,
            max_item_count=top
        ))
        
        return items
    except Exception as e:
        logger.error(f"회의 목록 조회 실패: {e}")
        return []

def get_meeting(meeting_id):
    """특정 회의 정보를 조회합니다."""
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_MEETINGS_CONTAINER)
        
        return container.read_item(item=meeting_id, partition_key=meeting_id)
    except exceptions.CosmosResourceNotFoundError:
        logger.warning(f"회의 ID {meeting_id} 조회 실패: 문서 없음")
        return None
    except Exception as e:
        logger.error(f"회의 조회 실패: {e}")
        raise

def get_action_items(meeting_id):
    """특정 회의의 액션 아이템을 조회합니다."""
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_ACTION_ITEMS_CONTAINER)
        
        query = f"SELECT * FROM c WHERE c.meetingId = '{meeting_id}'"
        items = list(container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        return items
    except Exception as e:
        logger.error(f"액션 아이템 조회 실패: {e}")
        return []

def get_all_action_items():
    """모든 액션 아이템을 조회합니다."""
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_ACTION_ITEMS_CONTAINER)
        
        query = "SELECT * FROM c ORDER BY c.created_at DESC"
        items = list(container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        return items
    except Exception as e:
        logger.error(f"모든 액션 아이템 조회 실패: {e}")
        return []

def update_action_item(item_id, meeting_id, updates):
    """액션 아이템을 수정합니다."""
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_ACTION_ITEMS_CONTAINER)
        
        # 아이템 조회
        query = f"SELECT * FROM c WHERE c.id = '{item_id}' AND c.meetingId = '{meeting_id}'"
        items = list(container.query_items(
            query=query,
            partition_key=meeting_id
        ))
        
        if not items:
            raise ValueError(f"액션 아이템 ID {item_id}를 찾을 수 없습니다.")
        
        item = items[0]
        
        # 항목 업데이트
        for key, value in updates.items():
            item[key] = value
        
        # 항목 저장
        return container.replace_item(item=item["id"], body=item)
    except Exception as e:
        logger.error(f"액션 아이템 수정 실패: {e}")
        raise

def approve_action_item(item_id, meeting_id, final_assignee_id, reviewer_name=None):
    """액션 아이템을 승인하고 담당자를 할당합니다."""
    try:
        # 액션 아이템 업데이트
        update_result = update_action_item(item_id, meeting_id, {
            "finalAssigneeId": final_assignee_id,
            "approved": True,
            "status": "진행중"
        })
        
        # 승인 이력 저장
        if reviewer_name:
            save_approval_history(
                meeting_id=meeting_id,
                action_item_id=item_id,
                reviewer=reviewer_name,
                changes={
                    "finalAssigneeId": final_assignee_id,
                    "approved": True
                }
            )
        
        return update_result
    except Exception as e:
        logger.error(f"액션 아이템 승인 실패: {e}")
        raise

def update_action_item_status(item_id, meeting_id, status):
    """액션 아이템의 상태를 업데이트합니다."""
    return update_action_item(item_id, meeting_id, {"status": status})

def save_approval_history(meeting_id, action_item_id, reviewer, changes):
    """승인 이력을 저장합니다."""
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_HISTORY_CONTAINER)
        
        timestamp = datetime.utcnow().isoformat()
        history_id = f"history_{action_item_id}_{timestamp.replace(':', '-')}"
        
        history_item = {
            "id": history_id,
            "meetingId": meeting_id,
            "actionItemId": action_item_id,
            "reviewer": reviewer,
            "changes": changes,
            "timestamp": timestamp
        }
        
        container.create_item(body=history_item)
        return history_id
    except Exception as e:
        logger.error(f"승인 이력 저장 실패: {e}")
        raise

def save_audit_log(user_id, action_type, resource_id, resource_type, changes, metadata=None):
    """감사 로그를 저장합니다."""
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_AUDIT_CONTAINER)
        
        timestamp = datetime.utcnow().isoformat()
        log_id = f"audit_{resource_type}_{resource_id}_{timestamp.replace(':', '-')}"
        
        log_entry = {
            "id": log_id,
            "userId": user_id,
            "actionType": action_type,  # CREATE, UPDATE, APPROVE 등
            "resourceId": resource_id,
            "resourceType": resource_type,  # meeting, action_item 등
            "changes": changes,
            "metadata": metadata or {},
            "timestamp": timestamp
        }
        
        container.create_item(body=log_entry)
        return log_id
    except Exception as e:
        logger.error(f"감사 로그 저장 실패: {e}")
        raise

def apply_json_modification(action_item_id, meeting_id, original_json, mod_request, reviewer_name=None):
    """액션 아이템을 자연어 요청에 따라 수정합니다."""
    from services.openai_service import apply_json_modification as ai_apply_json_modification
    
    try:
        # OpenAI로 수정 요청
        modified = ai_apply_json_modification(original_json, mod_request)
        
        # 변경 사항 추출
        changes = {}
        original = json.loads(original_json) if isinstance(original_json, str) else original_json
        
        for key, value in modified.items():
            if key in original and original[key] != value:
                changes[key] = value
        
        # 액션 아이템 업데이트
        update_action_item(action_item_id, meeting_id, changes)
        
        # 수정 이력 기록
        if reviewer_name and changes:
            save_approval_history(
                meeting_id=meeting_id,
                action_item_id=action_item_id,
                reviewer=reviewer_name,
                changes=changes
            )
            
        return modified
    except Exception as e:
        logger.error(f"액션 아이템 수정 실패: {e}")
        raise

def update_meeting(meeting_id, updates):
    """회의 정보를 업데이트합니다."""
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_MEETINGS_CONTAINER)
        
        # 회의 조회
        meeting = container.read_item(item=meeting_id, partition_key=meeting_id)
        
        # 항목 업데이트
        for key, value in updates.items():
            meeting[key] = value
        
        # 수정 시간 업데이트
        meeting['updated_at'] = datetime.utcnow().isoformat()
        
        # 항목 저장
        result = container.replace_item(item=meeting["id"], body=meeting)
        logger.info(f"회의 업데이트 완료: {meeting_id}")
        return result
        
    except exceptions.CosmosResourceNotFoundError:
        logger.error(f"회의 ID {meeting_id}를 찾을 수 없습니다.")
        raise ValueError(f"회의 ID {meeting_id}를 찾을 수 없습니다.")
    except Exception as e:
        logger.error(f"회의 업데이트 실패: {e}")
        raise

# 인사정보 관리 함수들
def init_staff_data():
    """더미 인사정보 초기화"""
    try:
        staff_data = [
            {"id": "staff_1", "user_id": 1, "name": "김민수", "department": "개발팀", "position": "시니어 개발자", "email": "kimminsu@company.com", "skills": ["Python", "AI", "Backend"]},
            {"id": "staff_2", "user_id": 2, "name": "이영희", "department": "기획팀", "position": "프로젝트 매니저", "email": "leeyh@company.com", "skills": ["Project Management", "Communication", "Planning"]},
            {"id": "staff_3", "user_id": 3, "name": "박철수", "department": "개발팀", "position": "주니어 개발자", "email": "parkcs@company.com", "skills": ["JavaScript", "Frontend", "React"]},
            {"id": "staff_4", "user_id": 4, "name": "최지은", "department": "디자인팀", "position": "UI/UX 디자이너", "email": "choije@company.com", "skills": ["UI Design", "UX Research", "Figma"]},
            {"id": "staff_5", "user_id": 5, "name": "정하늘", "department": "마케팅팀", "position": "마케팅 전문가", "email": "junghn@company.com", "skills": ["Digital Marketing", "Analytics", "Content"]}
        ]
          # 기존 데이터가 있는지 확인
        existing_staff = get_all_staff()
        if not existing_staff:
            client = get_client()
            db = client.get_database_client(config.COSMOS_DB_NAME)
            container = db.get_container_client(config.COSMOS_STAFF_CONTAINER)
            
            for staff in staff_data:
                staff['created_at'] = datetime.now().isoformat()
                staff['updated_at'] = datetime.now().isoformat()
                staff['type'] = 'staff'
                container.create_item(staff)
            print("✅ 더미 인사정보 초기화 완료")
        else:
            print("📋 인사정보가 이미 존재합니다.")
            
    except Exception as e:
        print(f"❌ 인사정보 초기화 오류: {str(e)}")

def get_all_staff():
    """모든 인사정보 조회"""
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_STAFF_CONTAINER)
        
        query = "SELECT * FROM c ORDER BY c.name"
        items = list(container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return items
    except Exception as e:
        print(f"❌ 인사정보 조회 오류: {str(e)}")
        return []

def get_staff_by_id(staff_id):
    """ID로 특정 인사정보 조회"""    
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_STAFF_CONTAINER)
        
        query = "SELECT * FROM c WHERE c.id = @staff_id"
        parameters = [{"name": "@staff_id", "value": staff_id}]
        
        items = list(container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        
        return items[0] if items else None
    except Exception as e:
        print(f"❌ 인사정보 조회 오류: {str(e)}")
        return None

def update_staff(staff_id, updates):
    """인사정보 업데이트"""    
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_STAFF_CONTAINER)
        
        staff = get_staff_by_id(staff_id)
        if not staff:
            print(f"❌ 인사정보 ID {staff_id}를 찾을 수 없습니다.")
            return False
        
        # 업데이트 적용
        staff.update(updates)
        staff['updated_at'] = datetime.now().isoformat()
        
        # 저장
        container.upsert_item(staff)
        print(f"✅ 인사정보 {staff_id} 업데이트 완료")
        return True
        
    except Exception as e:
        print(f"❌ 인사정보 업데이트 오류: {str(e)}")
        return False

def add_staff(staff_data):
    """새로운 인사정보 추가"""
    try:
        # 새로운 ID 생성
        existing_staff = get_all_staff()
        max_user_id = max([s.get('user_id', 0) for s in existing_staff], default=0)
        
        new_staff = {
            "id": f"staff_{max_user_id + 1}",
            "user_id": max_user_id + 1,
            "name": staff_data.get('name', ''),
            "department": staff_data.get('department', ''),
            "position": staff_data.get('position', ''),
            "email": staff_data.get('email', ''),
            "skills": staff_data.get('skills', []),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "type": "staff"
        }
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_STAFF_CONTAINER)
        
        container.create_item(new_staff)
        print(f"✅ 새로운 인사정보 추가 완료: {new_staff['name']}")
        return new_staff['id']
        
    except Exception as e:
        print(f"❌ 인사정보 추가 오류: {str(e)}")
        return None

def delete_staff(staff_id):
    """인사정보 삭제"""
    try:
        staff = get_staff_by_id(staff_id)
        if not staff:
            print(f"❌ 인사정보 ID {staff_id}를 찾을 수 없습니다.")
            return False
        
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_STAFF_CONTAINER)
        
        container.delete_item(item=staff_id, partition_key=staff_id)
        print(f"✅ 인사정보 {staff_id} 삭제 완료")
        return True
        
    except Exception as e:
        print(f"❌ 인사정보 삭제 오류: {str(e)}")
        return False

def recommend_assignee_for_task(task_description, task_skills=None):
    """작업 내용에 따른 담당자 추천"""
    try:
        all_staff = get_all_staff()
        if not all_staff:
            return None
        
        # 간단한 키워드 기반 매칭
        task_lower = task_description.lower()
        
        # 스킬 기반 점수 계산
        scored_staff = []
        for staff in all_staff:
            score = 0
            staff_skills = [skill.lower() for skill in staff.get('skills', [])]
            
            # 작업 설명에서 스킬 키워드 매칭
            for skill in staff_skills:
                if skill in task_lower:
                    score += 3
            
            # 부서별 가중치
            department = staff.get('department', '').lower()
            if 'development' in task_lower or 'code' in task_lower or 'programming' in task_lower or '개발' in task_lower:
                if '개발' in department:
                    score += 2
            elif 'design' in task_lower or 'ui' in task_lower or 'ux' in task_lower or '디자인' in task_lower:
                if '디자인' in department:
                    score += 2
            elif 'marketing' in task_lower or 'promotion' in task_lower or '마케팅' in task_lower:
                if '마케팅' in department:
                    score += 2
            elif 'plan' in task_lower or 'manage' in task_lower or '기획' in task_lower:
                if '기획' in department:
                    score += 2
            
            scored_staff.append((staff, score))
        
        # 점수순으로 정렬하여 최고 점수 반환
        scored_staff.sort(key=lambda x: x[1], reverse=True)
        
        if scored_staff and scored_staff[0][1] > 0:
            return scored_staff[0][0]
        else:
            # 매칭되는 스킬이 없으면 첫 번째 직원 반환
            return all_staff[0]
            
    except Exception as e:
        print(f"❌ 담당자 추천 오류: {str(e)}")
        return None

# 채팅 히스토리 관리 함수들
def save_chat_history(session_id, messages, summary=None):
    """채팅 히스토리를 저장합니다."""
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_CHAT_HISTORY_CONTAINER)
        
        timestamp = datetime.now()
        chat_id = f"chat_{session_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # 대화 요약 생성 (첫 번째 사용자 메시지 활용)
        if not summary and messages:
            user_messages = [msg for msg in messages if msg.get('role') == 'user']
            if user_messages:
                first_message = user_messages[0].get('content', '')
                summary = first_message[:50] + "..." if len(first_message) > 50 else first_message
            else:
                summary = "새로운 채팅"
        
        chat_history = {
            "id": chat_id,
            "type": "chat_history",
            "session_id": session_id,
            "messages": messages,
            "summary": summary or "새로운 채팅",
            "timestamp": timestamp.isoformat(),
            "created_at": timestamp.isoformat(),
            "message_count": len(messages)
        }
        
        container.create_item(body=chat_history)
        print(f"✅ 채팅 히스토리 저장 완료: {chat_id}")
        return chat_id
        
    except Exception as e:
        print(f"❌ 채팅 히스토리 저장 오류: {str(e)}")
        return None

def get_chat_histories(session_id=None, limit=20):
    """채팅 히스토리 목록을 조회합니다."""
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_CHAT_HISTORY_CONTAINER)
        
        if session_id:
            query = "SELECT * FROM c WHERE c.type = 'chat_history' AND c.session_id = @session_id ORDER BY c.timestamp DESC"
            parameters = [{"name": "@session_id", "value": session_id}]
        else:
            query = "SELECT * FROM c WHERE c.type = 'chat_history' ORDER BY c.timestamp DESC"
            parameters = []
        
        items = list(container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
            max_item_count=limit
        ))
        
        print(f"✅ 채팅 히스토리 조회 완료: {len(items)}개")
        return items
        
    except Exception as e:
        print(f"❌ 채팅 히스토리 조회 오류: {str(e)}")
        return []

def get_chat_history_by_id(chat_id):
    """특정 채팅 히스토리를 조회합니다."""
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_CHAT_HISTORY_CONTAINER)
        
        chat_history = container.read_item(item=chat_id, partition_key=chat_id)
        print(f"✅ 채팅 히스토리 조회 완료: {chat_id}")
        return chat_history
        
    except exceptions.CosmosResourceNotFoundError:
        print(f"❌ 채팅 히스토리를 찾을 수 없습니다: {chat_id}")
        return None
    except Exception as e:
        print(f"❌ 채팅 히스토리 조회 오류: {str(e)}")
        return None

def delete_chat_history(chat_id):
    """채팅 히스토리를 삭제합니다."""
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_CHAT_HISTORY_CONTAINER)
        
        container.delete_item(item=chat_id, partition_key=chat_id)
        print(f"✅ 채팅 히스토리 삭제 완료: {chat_id}")
        return True
        
    except exceptions.CosmosResourceNotFoundError:
        print(f"❌ 삭제할 채팅 히스토리를 찾을 수 없습니다: {chat_id}")
        return False
    except Exception as e:
        print(f"❌ 채팅 히스토리 삭제 오류: {str(e)}")
        return False

def update_chat_history_summary(chat_id, new_summary):
    """채팅 히스토리 요약을 업데이트합니다."""
    try:
        client = get_client()
        db = client.get_database_client(config.COSMOS_DB_NAME)
        container = db.get_container_client(config.COSMOS_CHAT_HISTORY_CONTAINER)
        
        chat_history = container.read_item(item=chat_id, partition_key=chat_id)
        chat_history['summary'] = new_summary
        chat_history['updated_at'] = datetime.now().isoformat()
        
        container.replace_item(item=chat_id, body=chat_history)
        print(f"✅ 채팅 히스토리 요약 업데이트 완료: {chat_id}")
        return True
        
    except Exception as e:
        print(f"❌ 채팅 히스토리 요약 업데이트 오류: {str(e)}")
        return False