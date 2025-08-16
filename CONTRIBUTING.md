# Contributing to flowpaths

Thanks for your interest in improving flowpaths! This guide explains how to contribute code, examples, documentation, and tests, plus how to run everything locally.

## Ways to contribute

- Report bugs and request features via GitHub Issues.
- Improve documentation (tutorials, how-tos, API docstrings, and references).
- Add or improve examples in `examples/` (small, runnable, well-commented).
- Contribute code: new features, performance improvements, and fixes.
- Add tests in `tests/` to cover new behavior and edge cases.

## Development setup

Requirements:
- Python 3.8+ (the package targets 3.8 and newer)
- Git

Recommended local setup (macOS / Linux / WSL):

```bash
# 1) Fork the repo on GitHub, then clone your fork
git clone https://github.com/algbio/flowpaths.git
cd flowpaths

# 2) Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # zsh/bash

# 3) Install the package in editable mode (installs runtime deps from pyproject)
pip install -e .

# 4) Install test tooling
pip install pytest
```

Tips:
- Keep branches small and focused (e.g., `feat/k-min-path-error-speedups`, `fix/mfd-edge-case`).
- Aim for clear commit messages and PR descriptions.

## Repository structure

The top-level repo layout is the following:

```
flowpaths/                 # Python package source (imported as `flowpaths`)
  utils/                   # Utilities (e.g., drawing, logging, graph helpers)
  __init__.py              # Public API exports
  ...                      # Solvers and core modules

docs/                      # MkDocs site (Markdown pages, assets)

examples/                  # Small, runnable scripts demonstrating usage

tests/                     # Pytest suite (unit tests + tiny graph inputs)

.github/                   # GitHub workflows and repo meta (if present)

mkdocs.yml                 # Docs site configuration and navigation
pyproject.toml             # Package metadata and runtime deps
requirements.txt           # Pinned runtime deps for local installs
README.md, LICENSE         # Project overview and license

```

Where to put things:
- New features/solvers: add code under `flowpaths/` and tests in `tests/`.
- New examples: add a small runnable script under `examples/`.
- Docs edits: update/add `docs/*.md` and register pages in `mkdocs.yml`.
- Graph fixtures for tests: use tiny graphs; store under `tests/` (e.g., `tests/cyclic_graphs/`).

## Running tests locally

The test suite lives in `tests/` and uses `pytest`.

```bash
# Run all tests
pytest -q

# Run a specific file or test expression
pytest -q tests/test_min_flow_decomp.py
pytest -q -k "least_abs_errors and not cycles"
```

Make sure new code is covered by tests and that tests are deterministic and fast. Prefer tiny graphs in unit tests and keep example-driven tests in `examples/` lightweight (these are run as part of the test `tests/test_examples.py`).

Optional coverage locally:
```bash
pip install pytest-cov
pytest --cov=flowpaths --cov-report=term-missing
```

## Running examples

Examples are in `examples/`. You can run any of them directly, for example:

```bash
python examples/min_flow_decomp.py
python examples/min_flow_decomp_cycles.py
python examples/least_abs_errors.py
```

If an example requires an external solver (e.g., Gurobi), it will mention it via `solver_options`. By default, the package uses the HiGHS solver (via `highspy`), which is installed with `pip install -e .`.

## Coding guidelines

- Follow PEP 8 style, add type hints where practical.
- Include docstrings for public functions/classes; briefly describe parameters, return values, and behavior.
- Keep functions focused; prefer small, composable helpers.
- Maintain backward compatibility when possible; if changing public APIs, note it in the PR and update docs/tests.
- Add tests for new functionality and edge cases.

Docstrings are part of our docs via `mkdocstrings`. Small code examples in docstrings are welcome when they clarify usage.

## Documentation: build and preview locally

We use MkDocs with the Material theme and mkdocstrings.

Install documentation requirements into your active virtualenv:
```bash
pip install \
  mkdocs \
  mkdocs-material \
  mkdocs-material-extensions \
  mkdocs-macros-plugin \
  mkdocstrings-python \
  mkdocs-autorefs \
  pymdown-extensions \
  mkdocs-get-deps \
  black
```

Serve the docs with live reload:
```bash
mkdocs serve
```
Then open the local URL (usually http://127.0.0.1:8000/). For a one-off build:
```bash
mkdocs build
```

### Adding or editing documentation pages

- Markdown sources live in `docs/`.
- Add new pages as `docs/<your-page>.md`.
- Register them in the navigation in `mkdocs.yml` under the appropriate section.
- For math, wrap inline with `$...$` and blocks with `$$...$$` (KaTeX is configured).
- For Python API docs pulled from docstrings, use mkdocstrings in Markdown:

  ```
  ::: flowpaths.MinFlowDecomp
  ```

MkDocs configuration references:
- Theme and plugins: `mkdocs.yml`
- Version macro: `docs/getversion.py` via `mkdocs-macros-plugin`

Before opening a PR that changes docs, please run `mkdocs serve` locally and check for warnings and broken links.

## Pull requests

1. Create a feature branch from the active development branch.
2. Implement the change with tests and docs updates as needed.
3. Run tests locally and ensure examples still run.
4. If docs changed, verify locally with `mkdocs serve`.
5. Open a PR with a clear title and description (what, why, how). Link related issues.

CI will run tests; please address any failures or review comments. Maintainers handle versioning and releases.

## Issue reporting

When filing an issue, please include:
- What you did (code snippet or example graph), what you expected, and what happened.
- Environment info (OS, Python version) and the `flowpaths` version.
- A minimal reproducible example if possible.

## License

By contributing, you agree that your contributions are licensed under the repository’s MIT License.

---

Questions? Open an issue or start a discussion in the repository. Thanks for helping improve flowpaths.
