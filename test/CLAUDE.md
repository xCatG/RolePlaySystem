# Testing Guidelines

## Test Organization
```
test/
└── python/
    ├── unit/          # Fast isolated tests
    │   ├── common/    # Models, storage, auth
    │   ├── server/    # Base handlers, decorators
    │   ├── chat/      # Chat-specific logic
    │   ├── auth/      # Auth module
    │   ├── scripter/  # Scripter module
    │   └── evaluator/ # Evaluator module
    ├── integration/   # Module interactions
    │   ├── storage/   # Backend integration
    │   ├── auth/      # OAuth flows
    │   └── handlers/  # Registration & DI
    ├── e2e/          # Full API tests
    │   ├── api/      # HTTP workflows
    │   └── websocket/# WebSocket tests
    └── fixtures/     # Shared test data
```

## Naming Conventions
- Unit tests: `test_<module_name>.py`
- Integration/E2E: `test_<feature>_flow.py`
- Test functions: `test_<what>_<condition>_<expected_result>`

## Coverage Targets
- **Unit Tests**: >90% coverage for core modules
- **Integration**: Critical paths (auth flows, storage backends)
- **E2E**: User journeys (registration → login → chat → evaluation)

## Test Stack
- **pytest**: Test runner with async support
- **httpx**: Async HTTP client for API tests
- **pytest-asyncio**: Async test support
- **factory-boy**: Test data generation
- **pytest-mock**: Mocking framework

## Performance Testing
```python
@pytest.mark.slow
def test_large_dataset_handling():
    """Mark slow tests to skip during rapid development"""
    pass
```

## Storage Testing
When testing storage backends:
- Use temporary directories for FileStorage
- Mock cloud storage clients (GCS, S3)
- Test both success and failure paths
- Verify lock behavior with concurrent operations

## Fixtures Best Practices
```python
# conftest.py
@pytest.fixture
async def auth_manager(tmp_path):
    """Create isolated auth manager for each test"""
    storage = FileStorage(config)
    return AuthManager(storage)

# Use fixtures for common test data
@pytest.fixture
def valid_user_data():
    return {"email": "test@example.com", "password": "secure123"}
```

## Current Test Status
- **FileStorage**: 92% coverage (production ready)
- **Auth/Models**: 80%+ coverage
- **Cloud Storage**: 0% (stubs only, validated via integration tests)
- **Evaluation**: 73% coverage (18 comprehensive tests)
- **Total**: 260+ tests, 54% overall coverage

## Evaluation Testing Patterns

### Mock Storage for Handler Tests
```python
@pytest.fixture
def mock_storage():
    """Create mock storage backend for evaluation tests."""
    storage = AsyncMock()
    storage.write = AsyncMock()
    storage.read = AsyncMock() 
    storage.list_keys = AsyncMock()
    return storage
```

### UUID Mocking for Predictable Tests
```python
# Mock UUID generation for consistent test results
with patch('role_play.evaluation.handler.uuid.uuid4') as mock_uuid:
    mock_uuid.return_value = Mock(__str__=lambda self: "abcd1234")
```

### Evaluation Test Coverage
- **Handler Tests**: Session evaluation flow, error handling, cleanup
- **Endpoint Tests**: Report retrieval, listing, creation
- **Storage Tests**: Report persistence, retrieval by ID
- **Error Scenarios**: Missing reports, storage failures, malformed data

## Running Tests
```bash
# All tests
pytest

# Run with make targets
make test                                 # Full suite with coverage
make test-no-coverage                     # Fast execution
make test-unit                            # Unit tests only
make test-evaluation                      # Evaluation module only

# Specific test execution
make test-specific TEST_PATH=test/python/unit/evaluation/

# Generate HTML coverage report
make test-coverage-html
```