# Contributing

Thank you for your interest in contributing to Upwork Learning!

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/Agent-Guidelines-for-Upwork-Learning-Projects.git
   cd Agent-Guidelines-for-Upwork-Learning-Projects
   ```
3. Install dependencies:
   ```bash
   uv sync --all-extras
   ```
4. Install pre-commit hooks:
   ```bash
   uv run pre-commit install
   ```

## Development Workflow

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes

3. Run tests and linting:
   ```bash
   pytest
   ruff check src/ tests/
   mypy src/
   ```

4. Commit your changes (follow conventional commits):
   ```bash
   git commit -m "feat: add new feature"
   ```

5. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

6. Open a Pull Request

## Code Style

- Follow PEP 8 guidelines
- Use type annotations for all functions
- Write docstrings for public APIs
- Keep functions small and focused

## Testing

- All new features must include tests
- All tests must pass before merging
- Aim for 80%+ code coverage

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Test changes
- `chore:` Build process or auxiliary tool changes

## Pull Request Process

1. Update documentation if needed
2. Add tests for new functionality
3. Ensure all checks pass
4. Request review from maintainers
5. Once approved, squash and merge

## Questions?

Feel free to open an issue for questions or discussions.
