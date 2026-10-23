# Contributing to Taskflow Pro

## 1. Development Environment Setup
```powershell
# 1. Clone the repository
git clone https://github.com/Shankar1234566/Taskflow.git
cd Taskflow

# 2. Activate Python virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Seed demo data
python seed.py

# 4. Run automated tests
pytest -v

# 5. Start development server
python run.py
```

## 2. Code Quality & Conventions
- **PEP 8**: Follow standard Python conventions.
- **Type Annotations**: Provide type annotations for all new service functions and models.
- **Test Coverage**: All new routes or services must be paired with pytest automated test cases under `tests/`.
- **Atomic Commits**: Keep Git commit messages clear and imperative (e.g. `feat: add burndown calculation`).
