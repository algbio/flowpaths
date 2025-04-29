import importlib.util
import pathlib
import pytest

EXAMPLES_DIR = pathlib.Path(__file__).parent.parent / "examples"

example_files = list(EXAMPLES_DIR.glob("**/*.py"))

@pytest.mark.parametrize("example_path", example_files)
def test_example(example_path):
    spec = importlib.util.spec_from_file_location(example_path.stem, example_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Call main() if it exists
    if hasattr(module, "main"):
        module.main()