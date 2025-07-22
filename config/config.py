import os
from dotenv import load_dotenv

load_dotenv()

# Azure Speech Service
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")

# Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

# Azure Blob Storage
AZURE_BLOB_CONNECTION_STRING = os.getenv("AZURE_BLOB_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "meeting-files")
AZURE_STORAGE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
AZURE_STORAGE_ACCOUNT_KEY = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

# Azure AI Search
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_ADMIN_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX", "meetings-index")

# Azure Cosmos DB
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DB_NAME = os.getenv("COSMOS_DB_NAME", "meetings-db")
COSMOS_MEETINGS_CONTAINER = os.getenv("COSMOS_MEETINGS_CONTAINER", "meetings")
COSMOS_ACTION_ITEMS_CONTAINER = os.getenv("COSMOS_ACTION_ITEMS_CONTAINER", "action-items")
COSMOS_HISTORY_CONTAINER = os.getenv("COSMOS_HISTORY_CONTAINER", "approval-history")
COSMOS_AUDIT_CONTAINER = os.getenv("COSMOS_AUDIT_CONTAINER", "audit-logs")

# 레거시 SQLite 설정 - 마이그레이션 후 제거 예정
DB_PATH = os.getenv("DB_PATH", "meetings.db")