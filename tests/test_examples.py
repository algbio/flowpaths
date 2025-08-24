import importlib.util
import os
import pathlib
import pytest

EXAMPLES_DIR = pathlib.Path(__file__).parent.parent / "examples"

example_files = list(EXAMPLES_DIR.glob("**/*.py"))

@pytest.fixture(scope="module", autouse=True)
def _suppress_draw():
    """Auto-used fixture to suppress graph rendering during tests.

    Replaces flowpaths.utils.draw with a no-op unless environment variable
    FP_ENABLE_DRAW is set (any non-empty value). This speeds up the example
    test suite and avoids requiring graphviz in CI when only logic is needed.
    """
    if os.environ.get("FP_ENABLE_DRAW"):
        # Allow real drawing
        yield
        return
    try:
        import flowpaths.utils as _utils
    except Exception:
        yield  # If import fails here, tests will surface the real issue later.
        return
    original = _utils.draw
    _utils.draw = lambda *a, **k: None  # type: ignore
    try:
        yield
    finally:
        _utils.draw = original  # restore


@pytest.mark.parametrize("example_path", example_files, ids=lambda path: path.name)
def test_example(example_path):
    spec = importlib.util.spec_from_file_location(example_path.stem, example_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if hasattr(module, "main"):
        module.main()

def teardown_module(module):

    # Look for pdf files in the current working directory.
    cwd = pathlib.Path.cwd()
    for pdf_file in cwd.glob("test_graph*.pdf"):
        try:
            pdf_file.unlink()
        except Exception as e:
            print(f"Failed to remove {pdf_file}: {e}")
