from __future__ import annotations

import os
import sys
from typing import Optional, Union

import libcst as cst


def transform_code(code: str) -> str:
    sys.path.append(os.getcwd())

    code = _flatten_imports(code)

    tree = cst.parse_module(code)
    wrapper = cst.metadata.MetadataWrapper(tree)
    tree = wrapper.visit(_PydanticV1Transformer())

    return tree.code


class _PydanticV1Transformer(cst.CSTTransformer):
    def __init__(self) -> None:
        ...

    def visit_Import(self, node: cst.Import) -> Optional[bool]:
        for import_alias in node.names:
            imported_module = _to_str(import_alias.name)
            if imported_module == "pydantic" or imported_module.startswith("pydantic."):
                ...


def _flatten_imports(code: str) -> str:
    tree = cst.parse_module(code)
    wrapper = cst.metadata.MetadataWrapper(tree)
    tree = wrapper.visit(_FlattenImportsTransformer())
    return tree.code


class _FlattenImportsTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (cst.metadata.ParentNodeProvider,)

    def __init__(self) -> None:
        self._import_lines = {}

    def visit_Import(self, node: "Import") -> Optional[bool]:
        parent_node = self.get_metadata(cst.metadata.ParentNodeProvider, node)
        assert isinstance(parent_node, cst.SimpleStatementLine)

        import_info = {"type": "import", "imports": []}
        for import_alias in node.names:
            import_info["imports"].append(import_alias)

        if parent_node in self._import_lines:
            self._import_lines[parent_node].append(import_info)
        else:
            self._import_lines[parent_node] = [import_info]

    def leave_SimpleStatementLine(
        self, original_node: "SimpleStatementLine", updated_node: "SimpleStatementLine"
    ) -> Union[
        "BaseStatement", cst.FlattenSentinel["BaseStatement"], cst.RemovalSentinel
    ]:
        if original_node not in self._import_lines:
            return updated_node

        nodes = []
        for import_info in self._import_lines[original_node]:
            for import_ in import_info["imports"]:
                nodes.append(
                    cst.SimpleStatementLine(
                        body=[
                            cst.Import(
                                names=[
                                    import_.with_changes(
                                        comma=cst.MaybeSentinel.DEFAULT
                                    )
                                ]
                            )
                        ]
                    )
                )
        return cst.FlattenSentinel(nodes=nodes)


def _to_str(attribute: cst.Attribute | cst.Name) -> str:
    if isinstance(attribute, cst.Name):
        return attribute.value
    else:
        assert isinstance(attribute.value, (cst.Attribute, cst.Name))
        return _to_str(attribute.value) + "." + "." + attribute.attr.value
