# Role Play System - Testing Guide

This directory contains comprehensive tests for the Role Play System backend implementation.

## Test Structure

The test suite is organized by language and test type to support future multi-language development:

```
test/
├── python/                    # Python backend tests
│   ├── unit/                 # Fast isolated unit tests
│   │   └── common/          # Tests for shared models, storage, auth
│   ├── integration/         # Cross-module interaction tests
│   │   ├── storage/        # Storage backend integration tests
│   │   └── auth/           # Authentication workflow tests
│   ├── e2e/                # End-to-end API tests (future)
│   ├── fixtures/           # Test data factories and helpers
│   ├── conftest.py         # Pytest configuration and shared fixtures
│   └── __init__.py
├── ts/                     # TypeScript frontend tests (future)
├── android/               # Android client tests (future)
└── README.md             # This file
```

## Prerequisites

1. **Python Environment**: Python 3.10+ with virtual environment
2. **Dependencies**: Install test dependencies in virtual environment

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install pydantic passlib[bcrypt] pyjwt pytest pytest-asyncio pytest-cov
```

## Running Tests

### Quick Start

```bash
# From project root
cd /path/to/rps
source venv/bin/activate
pytest test/python/
```

### Test Categories

```bash
# Unit tests only (fast)
pytest test/python/unit/ -v

# Integration tests only
pytest test/python/integration/ -v

# Specific module tests
pytest test/python/unit/common/test_models.py -v
pytest test/python/integration/auth/ -v

# With coverage report
pytest test/python/ --cov=src/python/role_play/common --cov-report=html
```

### Test Markers

```bash
# Run only integration tests
pytest -m integration

# Run only unit tests  
pytest -m unit

# Skip slow tests
pytest -m "not slow"

# Run only auth-related tests
pytest -m auth
```

## Test Configuration

Test configuration is managed in `/pytest.ini`:

- **Test Discovery**: Automatically finds `test_*.py` files
- **Coverage**: Tracks code coverage with 40% minimum threshold
- **Async Support**: Handles async test functions automatically
- **Markers**: Categorizes tests by type and functionality

## Coverage Reports

After running tests with coverage:

```bash
# View coverage summary in terminal
pytest test/python/ --cov=src/python/role_play/common

# Generate HTML report
pytest test/python/ --cov=src/python/role_play/common --cov-report=html

# Open HTML report
open test/python/htmlcov/index.html
```

## Test Data and Fixtures

### Factories

Use test data factories for consistent test objects:

```python
from test.python.fixtures.factories import UserFactory, UserAuthMethodFactory

# Create test users
user = UserFactory.create(username="testuser")
admin = UserFactory.create_admin()

# Create auth methods
auth_method = UserAuthMethodFactory.create_local_auth(user)
oauth_method = UserAuthMethodFactory.create_google_auth(user)
```

### Shared Fixtures

Available in `conftest.py`:

- `temp_dir`: Temporary directory for file operations
- `file_storage`: FileStorage instance with temp directory
- `auth_manager`: AuthManager instance for testing
- `sample_user_data`: Sample user data dictionary

## Writing Tests

### Unit Tests

Unit tests should be fast, isolated, and test single components:

```python
import pytest
from role_play.common.models import User, UserRole

class TestUser:
    def test_user_creation_with_defaults(self):
        user = User(
            id="test-123",
            username="testuser",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        assert user.role == UserRole.USER
        assert user.is_active is True
```

### Integration Tests

Integration tests verify component interactions:

```python
import pytest
from pathlib import Path

@pytest.mark.integration
class TestFileStorageIntegration:
    @pytest.mark.asyncio
    async def test_complete_user_lifecycle(self):
        # Test create, read, update, delete workflow
        pass
```

### Async Tests

Use `@pytest.mark.asyncio` for async test functions:

```python
@pytest.mark.asyncio
async def test_auth_manager_registration(auth_manager):
    user, token = await auth_manager.register_user(
        username="testuser",
        password="password"
    )
    assert user.username == "testuser"
    assert token is not None
```

## Current Test Coverage

As of latest run:

- **Total Coverage**: 92.53%
- **AuthManager**: 97% coverage
- **FileStorage**: 88% coverage  
- **Models**: 100% coverage
- **Exceptions**: 100% coverage
- **Total Tests**: 98 tests passing

## Performance Considerations

- **Unit tests**: Should run in <1 second total
- **Integration tests**: May take several seconds due to file I/O
- **Performance tests**: Marked with `@pytest.mark.slow`

Use `-m "not slow"` to skip performance tests during development.

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure you're running from project root with activated venv
2. **Permission Errors**: Temporary directories may need cleanup
3. **Async Warnings**: Update pytest-asyncio if you see async fixture warnings

### Debugging Tests

```bash
# Run with verbose output and stop on first failure
pytest test/python/ -v -x

# Run specific test with print statements
pytest test/python/unit/common/test_models.py::TestUser::test_user_creation -v -s

# Run with pdb debugger on failures
pytest test/python/ --pdb
```

## Adding New Tests

1. **Choose appropriate directory**: `unit/` for isolated tests, `integration/` for workflows
2. **Follow naming convention**: `test_<module_name>.py` 
3. **Use appropriate markers**: `@pytest.mark.unit`, `@pytest.mark.integration`
4. **Leverage fixtures**: Use existing fixtures from `conftest.py`
5. **Update coverage**: Aim to maintain >90% coverage for new code

## Future Enhancements

- **E2E Tests**: Full API testing with HTTP client
- **Performance Benchmarks**: Automated performance regression testing  
- **Database Tests**: Integration tests with real database backends
- **Concurrent Tests**: Multi-user scenario testing
- **Frontend Tests**: TypeScript/JavaScript test integration