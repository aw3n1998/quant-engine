# Test Suite for Crypto Quant Terminal

## Setup

### Install Test Dependencies

```bash
pip install -r requirements.txt
```

This includes:
- `pytest>=7.4.0` - Testing framework
- `pytest-asyncio>=0.21.0` - Async test support
- `pytest-cov>=4.1.0` - Coverage reports
- `black>=23.7.0` - Code formatter
- `mypy>=1.5.0` - Type checker

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Tests with Verbose Output
```bash
pytest -v
```

### Run Specific Test File
```bash
pytest tests/unit/test_data_validation.py
```

### Run Specific Test Class
```bash
pytest tests/unit/test_data_validation.py::TestDataValidation
```

### Run Specific Test Function
```bash
pytest tests/unit/test_data_validation.py::TestDataValidation::test_valid_ohlcv_data
```

### Run Tests by Marker
```bash
pytest -m unit        # Run only unit tests
pytest -m integration # Run only integration tests
pytest -m async       # Run only async tests
```

## Coverage Report

### Generate Coverage Report
```bash
pytest --cov=app --cov-report=html
```

This generates an HTML coverage report in `htmlcov/index.html`

### View Coverage Summary
```bash
pytest --cov=app --cov-report=term-missing
```

## Code Style & Type Checking

### Format Code with Black
```bash
black app/ tests/
```

### Check Type Hints with MyPy
```bash
mypy app/ --ignore-missing-imports
```

## Directory Structure

```
tests/
├── __init__.py
├── conftest.py                 # Shared fixtures and configuration
├── fixtures/
│   └── __init__.py
├── unit/
│   ├── __init__.py
│   ├── test_data_validation.py
│   ├── test_indicator_calculations.py
│   ├── test_strategy_*.py       # Strategy tests
│   └── test_engine_*.py         # Engine tests
└── integration/
    ├── __init__.py
    ├── test_backtesting.py
    └── test_api_endpoints.py
```

## Test Coverage Goals

- **Phase 1**: Data validation (100% coverage)
- **Phase 2**: Indicator calculations (90% coverage)  
- **Phase 3**: Strategy logic (85% coverage)
- **Phase 4**: Engine implementations (80% coverage)
- **Overall Target**: >80% code coverage

## CI/CD Integration

Tests are automatically run on each commit via GitHub Actions. See `.github/workflows/test.yml` for configuration.

## Writing New Tests

### Basic Test Template
```python
import pytest
from app.module import function

class TestMyFeature:
    """Test MyFeature functionality."""
    
    def test_basic_functionality(self):
        """Test basic functionality."""
        result = function()
        assert result is not None
    
    @pytest.mark.async
    async def test_async_functionality(self):
        """Test async functionality."""
        result = await async_function()
        assert result == expected
```

### Using Fixtures
```python
def test_with_sample_data(sample_ohlcv_data):
    """Test using sample OHLCV data fixture."""
    df = sample_ohlcv_data
    assert len(df) == 100
    assert set(df.columns) >= {"open", "high", "low", "close", "volume"}
```

### Marking Tests
```python
@pytest.mark.unit
def test_unit_test():
    pass

@pytest.mark.integration
def test_integration_test():
    pass

@pytest.mark.slow
def test_slow_operation():
    pass

@pytest.mark.async
async def test_async_code():
    pass
```

## Troubleshooting

### Import Errors
Ensure you're running pytest from the `backend/` directory:
```bash
cd backend
pytest
```

### Async Test Failures
Make sure `pytest-asyncio` is installed and `asyncio_mode = auto` is set in `pytest.ini`.

### Fixture Not Found
Fixtures are defined in `conftest.py`. Ensure the file exists in the test directory you're running from.
