import pathlib

import pytest
import yaml

from codemodpydanticv1 import transform_code


def get_test_cases(file: str) -> list[dict]:
    with open(pathlib.Path(__file__).parent / file) as f:
        test_cases = yaml.safe_load(f)
    return test_cases


@pytest.mark.parametrize("test_case", get_test_cases("test_cases.yml"))
def test_transform_code(test_case: dict) -> None:
    print(test_case["input"])
    assert transform_code(test_case["input"]) == test_case["output"]


@pytest.mark.parametrize("test_case", get_test_cases("test_cases.yml"))
def test_transform_code_idempotent(test_case: dict) -> None:
    print(test_case["input"])
    assert transform_code(transform_code(test_case["input"])) == test_case["output"]
