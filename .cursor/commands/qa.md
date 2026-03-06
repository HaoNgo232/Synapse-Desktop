# qa
This workflow automates the execution of code formatting, linting, type checking, and unit testing to ensure the codebase remains clean and bug-free.

// turbo-all
1. Format code with Ruff
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff format .
```

2. Lint code and auto-fix with Ruff
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --fix .
```

3. Type-check with Pyrefly
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pyrefly check
```

4. Run unit tests with Pytest
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v
```