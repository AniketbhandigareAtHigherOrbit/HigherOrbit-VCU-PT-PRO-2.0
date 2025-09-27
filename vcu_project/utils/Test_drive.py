from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

# Service account info directly as a Python dict
SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": "driveupload-473408",
    "private_key_id": "4cf77251ea1641f0ba61eb6896fb8f1d7f09fadd",
    "private_key": """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDZDdkULxl+gMVl
...
DGb7P09l/r9GGXd1SwCtSkGc
-----END PRIVATE KEY-----""",
    "client_email": "h-orbit-295@driveupload-473408.iam.gserviceaccount.com",
    "client_id": "103708115471285477252",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/h-orbit-295%40driveupload-473408.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com"
}

# Define the scopes
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Create credentials from dict
credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO, scopes=SCOPES
)

# Build the Drive API client
service = build('drive', 'v3', credentials=credentials)

# File to upload
file_path = '/home/orbit/VCU-PT-PRO-2.0/vcu_project/utils/logs/2025-09-26_data.csv'
file_name = '2025-09-26_data.csv'

media = MediaFileUpload(file_path, resumable=True)

# Folder ID from your Shared Drive
SHARED_DRIVE_FOLDER_ID = '1rWv4claa-njEo6cPeuHWj78lqX3kR5vn'

file_metadata = {
    'name': file_name,
    'parents': [drive_pi]
}

# Upload the file
file = service.files().create(
    body=file_metadata,
    media_body=media,
    fields='id',
    supportsAllDrives=True
).execute()

print(f'File uploaded successfully. File ID: {file.get("id")}')
