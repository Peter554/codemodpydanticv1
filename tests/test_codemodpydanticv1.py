import pytest
import yaml
import pathlib

from codemodpydanticv1 import transform_code, _flatten_imports


def get_test_cases(file: str) -> list[dict]:
    with open(pathlib.Path(__file__).parent / file) as f:
        test_cases = yaml.safe_load(f)
    return test_cases


# @pytest.mark.parametrize("test_case", get_test_cases("test_cases.yml"))
# def test_transform_code(test_case: dict) -> None:
#     assert transform_code(test_case["input"]) == test_case["output"]
#


@pytest.mark.parametrize("test_case", get_test_cases("test_cases_flatten_imports.yml"))
def test_flatten_imports(test_case: dict) -> None:
    assert _flatten_imports(test_case["input"]) == test_case["output"]
