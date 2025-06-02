# Data Directory

This directory is used for **runtime data storage** when using file-based storage backend.

## Important: Static Resources Moved

Static resources like `scenarios.json` have been moved to `src/python/role_play/resources/` to be properly packaged with the application.

## Current Usage

When `STORAGE_TYPE=file`, this directory stores:
- User profiles
- Chat logs
- Session data
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