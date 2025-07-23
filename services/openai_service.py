import json
import re
import time
import logging
from azure.cognitiveservices.speech import SpeechConfig, AudioConfig, SpeechRecognizer
from openai import AzureOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
import config.config as config
from services.search_service import search_documents
from config.logging_config import (
    log_error_with_context,
    log_performance,
    log_azure_service_call,
)

# 로깅 설정
logger = logging.getLogger("openai_service")


def mask_sensitive_info(text: str) -> str:
    """민감정보를 마스킹합니다."""
    # 주민등록번호 패턴 마스킹
    text = re.sub(r"\d{6}[-\s]?[1-4]\d{6}", "******-*******", text)

    # 전화번호 패턴 마스킹
    text = re.sub(r"01[016789][-\s]?\d{3,4}[-\s]?\d{4}", "010-****-****", text)

    # 이메일 패턴 마스킹
    text = re.sub(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "****@****.com", text
    )

    # 계좌번호 패턴 마스킹
    text = re.sub(
        r"\d{2,6}[-\s]?\d{2,6}[-\s]?\d{2,6}[-\s]?\d{2,6}", "****-****-****", text
    )

    return text


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def transcribe_audio(file_path: str) -> str:
    """오디오 파일을 텍스트로 변환합니다. 파일 길이와 무관하게 안정적으로 동작합니다."""
    start_time = time.time()
    try:
        logger.info(f"음성 파일 변환 시작: {file_path}")
        speech_config = SpeechConfig(
            subscription=config.AZURE_SPEECH_KEY, region=config.AZURE_SPEECH_REGION
        )
        speech_config.speech_recognition_language = "ko-KR"
        audio_input = AudioConfig(filename=file_path)
        recognizer = SpeechRecognizer(speech_config, audio_input)

        done = False
        results = []

        def recognized(evt):
            if evt.result.reason.name == "RecognizedSpeech":
                results.append(evt.result.text)

        def stop_cb(evt):
            """세션이 중지되면 done 플래그를 설정합니다."""
            logger.info(f"음성 인식 세션 종료: {evt}")
            nonlocal done
            done = True

        recognizer.recognized.connect(recognized)
        recognizer.session_started.connect(
            lambda evt: logger.info("음성 인식 세션 시작")
        )
        recognizer.session_stopped.connect(stop_cb)
        recognizer.canceled.connect(stop_cb)

        recognizer.start_continuous_recognition()
        while not done:
            time.sleep(0.5)  # 완료될 때까지 대기

        recognizer.stop_continuous_recognition()

        result_text = "\n".join(results)
        duration = time.time() - start_time

        log_azure_service_call(
            logger,
            "Azure Speech Service",
            "transcribe_audio",
            duration,
            True,
            None,
            f"Transcribed {len(result_text)} characters",
        )
        log_performance(
            logger,
            "audio_transcription",
            duration,
            f"Output length: {len(result_text)} characters",
        )

        logger.info(f"음성 파일 변환 완료: {len(result_text)} 글자")
        return result_text
    except Exception as e:
        duration = time.time() - start_time
        log_error_with_context(
            logger, e, f"Audio transcription failed for file: {file_path}"
        )
        log_azure_service_call(
            logger,
            "Azure Speech Service",
            "transcribe_audio",
            duration,
            False,
            None,
            f"Error: {str(e)}",
        )
        logger.error(f"음성 파일 변환 오류: {e}")
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def summarize_and_extract(text: str) -> dict:
    """회의록을 요약하고 액션 아이템을 추출합니다."""
    start_time = time.time()
    try:  # 민감정보 마스킹 적용
        masked_text = mask_sensitive_info(text)
        logger.info("민감정보 마스킹 적용 완료")

        client = AzureOpenAI(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
        )

        prompt = f"""
회의록을 읽고 JSON 형식으로 회의 제목(meetingTitle), 회의 요약(summary), 참석자(participants), 액션 아이템 리스트(actionItems)를 추출하세요.

추출 규칙:
1. 회의 제목: 회의의 핵심 주제를 5~10단어로 요약하여 생성
2. 회의 요약: 주요 논의 내용과 결정사항을 2-3문장으로 요약
3. 참석자: 회의록에서 언급된 모든 참석자의 이름을 배열로 추출 (예: ["김민수", "이영희", "박철수"])
4. 액션 아이템: 모든 업무, 결정사항, 제안, 요청, 일정을 추출

액션 아이템이 명확히 표기되지 않더라도, 회의 내용·업무 맥락·참석자 역할·유사 이름을 분석해 반드시 액션 아이템과 담당자를 추론·추천하세요.
논의된 모든 업무, 결정사항, 제안, 요청, 일정 등은 반드시 액션아이템으로 추출하세요.
각 아이템은 id, description, dueDate(YYYY-MM-DD), recommendedAssigneeId 필드를 포함합니다.
recommendedAssigneeId는 회의에서 언급된 실제 참석자 이름이나 담당자 이름을 정확히 추출하세요. 숫자 ID 대신 실제 이름을 사용하세요.
담당자 이름이 명확하지 않은 경우, 업무 내용과 맥락을 기반으로 적합한 역할(예: "개발팀", "QA팀", "마케팅팀" 등)을 추천하세요.

응답 형식:
{{
  "meetingTitle": "회의 제목",
  "summary": "회의 요약",
  "participants": ["참석자1", "참석자2", "참석자3"],
  "actionItems": [
    {{
      "id": 1,
      "description": "업무 설명",
      "dueDate": "YYYY-MM-DD",
      "recommendedAssigneeId": "담당자명"
    }}
  ]
}}

회의록:
\"\"\"{masked_text}\"\"\"
"""

        logger.info("OpenAI API 요청 시작")
        api_start = time.time()
        response = client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        )
        api_duration = time.time() - api_start
        content = response.choices[0].message.content

        log_azure_service_call(
            logger,
            "Azure OpenAI",
            "chat_completion",
            api_duration,
            True,
            None,
            f"Model: {config.AZURE_OPENAI_DEPLOYMENT}",
        )
        logger.info("OpenAI API 응답 수신 완료")

        # 코드블록만 추출
        if "```json" in content:
            content = content.split("```json", 1)[1]
            content = content.split("```", 1)[0].strip()
        elif content.strip().startswith("```"):
            content = content.strip().split("\n", 1)[1]
            content = content.rsplit("```", 1)[0].strip()

        try:
            result = json.loads(content)
            total_duration = time.time() - start_time

            log_performance(
                logger,
                "meeting_summarization_complete",
                total_duration,
                f"Input: {len(text)} chars, Output: {len(result.get('actionItems', []))} actions",
            )
            logger.info(f"회의 제목: {result.get('meetingTitle')}")
            logger.info(f"액션 아이템 수: {len(result.get('actionItems', []))}")
            return result

        except json.JSONDecodeError as e:
            log_error_with_context(
                logger, e, f"Invalid JSON response from OpenAI: {content[:200]}..."
            )
            logger.error(f"OpenAI 응답이 올바른 JSON이 아닙니다: {e}")
            logger.debug(f"응답 내용: {content}")
            raise RuntimeError(f"OpenAI 응답이 올바른 JSON이 아닙니다: {e}")

    except Exception as e:
        total_duration = time.time() - start_time
        log_error_with_context(logger, e, "Meeting summarization failed")
        log_azure_service_call(
            logger,
            "Azure OpenAI",
            "chat_completion",
            total_duration,
            False,
            None,
            f"Error: {str(e)}",
        )
        logger.error(f"회의록 요약 및 액션 아이템 추출 오류: {e}")
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def apply_json_modification(original_json_str: str, mod_request: str) -> dict:
    """기존 요약/추출 결과(JSON)를 사용자의 자연어 요청에 따라 수정합니다."""
    try:
        logger.info(f"자연어 수정 요청 처리 시작: {mod_request[:50]}...")
        client = AzureOpenAI(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
        )

        prompt = f"""
        기존 JSON 데이터를 아래 '수정 요청'에 따라 변경하고, 최종 JSON 객체만 반환하세요.
        설명, 코드블록, 마크다운 없이 순수 JSON만 출력해야 합니다.

        [기존 데이터]
        ```json
        {original_json_str}
        ```

        [수정 요청]
        "{mod_request}"

        [수정된 최종 JSON]
        """
        response = client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content
        result = json.loads(content)
        logger.info("자연어 수정 요청 처리 완료")
        return result
    except Exception as e:
        logger.error(f"자연어 수정 요청 처리 오류: {e}")
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def ask_question(all_text: str, question: str) -> str:
    """회의록을 기반으로 질문에 답변합니다."""
    try:
        logger.info(f"질문 처리 시작: {question}")
        # 민감정보 마스킹 적용
        masked_text = mask_sensitive_info(all_text)

        client = AzureOpenAI(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
        )

        prompt = f"다음 회의록 및 액션아이템을 참고하여 사용자의 질문에 답변하세요.\n\n회의록:\n{masked_text}\n\n질문: {question}\n답변:"
        response = client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        )
        answer = response.choices[0].message.content.strip()
        logger.info(f"질문 처리 완료: {len(answer)} 글자")
        return answer
    except Exception as e:
        logger.error(f"질문 처리 오류: {e}")
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def ask_question_with_search(query: str) -> str:
    """검색을 통해 관련 회의록을 찾아 질문에 답변합니다."""
    try:
        logger.info(f"검색 기반 질문 처리 시작: {query}")
        # Azure AI Search에서 관련 문서 검색
        docs = search_documents(query)
        if not docs:
            logger.warning("검색 결과 없음")
            return "관련 회의록을 찾을 수 없습니다. 다른 질문을 시도해보세요."

        # 민감정보 마스킹 적용
        masked_contents = [mask_sensitive_info(doc["content"]) for doc in docs]
        context = "\n\n".join(masked_contents)

        prompt = f"""다음 회의록 및 액션아이템을 참고하여 사용자의 질문에 답변하세요.

검색된 회의록:
{context}

질문: {query}
답변:"""
        client = AzureOpenAI(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
        )
        response = client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        )
        answer = response.choices[0].message.content.strip()
        logger.info(f"검색 기반 질문 처리 완료: {len(answer)} 글자")
        return answer
    except Exception as e:
        logger.error(f"검색 기반 질문 처리 오류: {e}")
        raise


def recommend_best_assignee(
    task_description: str, staff_candidates: list, meeting_context: str = ""
) -> dict:
    """RAG 기반으로 최적의 담당자를 추천합니다."""
    try:
        logger.info("RAG 기반 담당자 추천 시작")

        # 후보 직원 정보를 문자열로 변환
        candidates_text = ""
        for i, staff in enumerate(staff_candidates, 1):
            skills_text = ", ".join(staff.get("skills", []))
            candidates_text += f"""
{i}. {staff.get('name')} (ID: {staff.get('user_id')})
   - 부서: {staff.get('department')}
   - 직책: {staff.get('position')}
   - 스킬: {skills_text}
   - 관련성 점수: {staff.get('relevance_score', 0):.2f}
"""

        prompt = f"""
다음 업무에 가장 적합한 담당자를 추천해주세요.

**업무 설명:**
{task_description}

**회의 맥락:**
{meeting_context}

**후보 직원들:**
{candidates_text}

**추천 기준:**
1. 업무 내용과 직원의 스킬 매칭도
2. 부서 및 직책의 적합성
3. 과거 유사 업무 경험 (관련성 점수 참고)

**응답 형식:**
다음 JSON 형식으로 응답해주세요:
{{
    "recommended_user_id": "추천할 직원의 user_id",
    "recommended_name": "추천할 직원의 이름",
    "confidence_score": 0.95,
    "reasoning": "추천 이유를 2-3문장으로 설명"
}}

가장 적합한 1명만 추천하고, 확신도(0.0-1.0)와 추천 이유를 포함해주세요.
"""

        logger.info("OpenAI API 요청 시작 (담당자 추천)")
        api_start = time.time()

        client = AzureOpenAI(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
        )

        response = client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert HR assistant specializing in task assignment and team optimization.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,  # 일관된 추천을 위해 낮은 temperature 사용
        )
        api_duration = time.time() - api_start

        log_azure_service_call(
            logger,
            "Azure OpenAI",
            "recommend_assignee",
            api_duration,
            True,
            None,
            f"Task: {task_description[:50]}...",
        )

        response_text = response.choices[0].message.content.strip()
        logger.info(f"담당자 추천 완료 (소요시간: {api_duration:.2f}초)")

        # JSON 파싱
        try:
            import json

            recommendation = json.loads(response_text)
            return recommendation
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 첫 번째 후보 반환
            if staff_candidates:
                return {
                    "recommended_user_id": staff_candidates[0].get("user_id"),
                    "recommended_name": staff_candidates[0].get("name"),
                    "confidence_score": 0.5,
                    "reasoning": "JSON 파싱 실패로 인한 첫 번째 후보 선택",
                }
            else:
                return None

    except Exception as e:
        logger.error(f"담당자 추천 실패: {e}")
        log_azure_service_call(
            logger,
            "Azure OpenAI",
            "recommend_assignee",
            0,
            False,
            str(e),
            f"Task: {task_description[:50]}...",
        )
        return None
