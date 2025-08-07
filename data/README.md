# Data Directory

This directory is used for **runtime data storage** when using file-based storage backend.

## Important: Static Resources

Static resources like `scenarios.json` should be in resources dir, and copied over to gcs/aws/disk storage folder under resources/ for the application to work properly

## Current Usage

When `STORAGE_TYPE=file`, this directory stores:
- User profiles
- Chat logs
- Session data
- Roleplay resources (character definition, scenario definition, scripts etc)
- Other runtime data

## Directory Structure (Runtime)

```
data/
├── users/
│   ├── {user_id}/
│   │   ├── profile
│   │   └── chat_logs/
│   │       └── {session_id}
│   └── ...
└── .lock/  # Lock files for concurrent access
```

## Note

This directory should be:
- Created before running the server with file storage
- Excluded from version control (except this README)
- Backed up regularly in production
- Have appropriate read/write permissions