from __future__ import annotations

import dataclasses
import functools
import importlib
import logging
import sys

import libcst as cst
from libcst import matchers as m


def transform_code(code: str) -> str:
    logging.debug(f"sys.path is {sys.path}")

    tree = cst.parse_module(code)
    wrapper = cst.MetadataWrapper(tree)
    tree = wrapper.visit(_PydanticV1Transformer())
    return tree.code


@dataclasses.dataclass(frozen=True)
class _NameReplacementRule:
    _name: str
    _replace: str

    def matches(self, name: cst.Name) -> bool:
        return name.value == self._name

    def replace(self, name: cst.Name) -> cst.Name:
        return cst.Name(self._replace)


@dataclasses.dataclass(frozen=True)
class _AttributeReplacementRule:
    _module: str
    _replace: str

    def matches(self, attribute: cst.Attribute) -> bool:
        s = _to_string(attribute)
        return s.startswith(self._module + ".")

    def replace(self, attribute: cst.Attribute) -> cst.Attribute:
        s = _to_string(attribute)
        return _to_attribute(
            self._replace.format(s.split(".", maxsplit=self._module.count(".") + 1)[-1])
        )


class _PydanticV1Transformer(m.MatcherDecoratableTransformer):
    METADATA_DEPENDENCIES = (cst.metadata.QualifiedNameProvider,)

    def __init__(self) -> None:
        super().__init__()
        self._name_replacements: list[_NameReplacementRule] = []
        self._attribute_replacements: list[_AttributeReplacementRule] = []

    @m.call_if_inside(m.Import())
    @m.leave(m.ImportAlias(m.Name("pydantic")))
    def update_pydantic_import(
        self, original_node: cst.ImportAlias, updated_node: cst.ImportAlias
    ) -> cst.ImportAlias:
        self._attribute_replacements.append(
            _AttributeReplacementRule(
                original_node.asname.name.value
                if original_node.asname
                else original_node.name.value,
                "pydantic_v1.{}",
            )
        )
        return cst.ImportAlias(
            name=_to_attribute("pydantic.v1"),
            asname=cst.AsName(cst.Name("pydantic_v1")),
        )

    @m.call_if_inside(m.Import())
    @m.leave(m.ImportAlias(m.Attribute(m.Name("pydantic"))))
    def update_pydantic_submodule_import(
        self, original_node: cst.ImportAlias, updated_node: cst.ImportAlias
    ) -> cst.ImportAlias:
        submodule_name = original_node.name.attr
        self._attribute_replacements.append(
            _AttributeReplacementRule(
                original_node.asname.name.value
                if original_node.asname
                else f"pydantic.{submodule_name.value}",
                f"pydantic_v1_{submodule_name.value}.{{}}",
            )
        )
        return cst.ImportAlias(
            name=_to_attribute(f"pydantic.v1.{submodule_name.value}"),
            asname=cst.AsName(cst.Name(f"pydantic_v1_{submodule_name.value}")),
        )

    @m.leave(m.ImportFrom(module=m.Name("pydantic")))
    def update_pydantic_importfrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        import_aliases: list[cst.ImportAlias] = []
        for import_alias in original_node.names:
            full_import = (
                _to_string(original_node.module) + "." + import_alias.name.value
            )
            if _is_module("pydantic.v1." + full_import.split(".", maxsplit=1)[1]):
                self._attribute_replacements.append(
                    _AttributeReplacementRule(
                        _to_string(
                            import_alias.asname.name
                            if import_alias.asname
                            else import_alias.name
                        ),
                        f"pydantic_v1_{import_alias.name.value}.{{}}",
                    )
                )
                import_aliases.append(
                    cst.ImportAlias(
                        name=import_alias.name,
                        asname=cst.AsName(
                            cst.Name(f"pydantic_v1_{import_alias.name.value}")
                        ),
                    )
                )
            else:
                self._name_replacements.append(
                    _NameReplacementRule(
                        import_alias.asname.name.value
                        if import_alias.asname
                        else import_alias.name.value,
                        self._rename_direct_import(import_alias.name.value),
                    )
                )
                import_aliases.append(
                    cst.ImportAlias(
                        name=import_alias.name,
                        asname=cst.AsName(
                            cst.Name(
                                self._rename_direct_import(import_alias.name.value)
                            )
                        ),
                    )
                )

        return cst.ImportFrom(
            module=_to_attribute("pydantic.v1"),
            names=import_aliases,
        )

    @m.leave(m.ImportFrom(module=m.Attribute(m.Name("pydantic"))))
    def update_pydantic_submodule_importfrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        submodule_name = original_node.module.attr
        import_aliases: list[cst.ImportAlias] = []
        for import_alias in original_node.names:
            self._name_replacements.append(
                _NameReplacementRule(
                    import_alias.asname.name.value
                    if import_alias.asname
                    else import_alias.name.value,
                    self._rename_direct_import(import_alias.name.value),
                )
            )
            import_aliases.append(
                cst.ImportAlias(
                    name=import_alias.name,
                    asname=cst.AsName(
                        cst.Name(self._rename_direct_import(import_alias.name.value))
                    ),
                )
            )
        return cst.ImportFrom(
            module=_to_attribute(f"pydantic.v1.{submodule_name.value}"),
            names=import_aliases,
        )

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        qualified_name = self._get_qualified_name(original_node)
        if (
            not qualified_name
            or qualified_name.source != cst.metadata.QualifiedNameSource.IMPORT
            or not qualified_name.name.startswith("pydantic.")
        ):
            return original_node

        for replacement in self._attribute_replacements:
            if replacement.matches(original_node):
                return replacement.replace(original_node)

        return original_node

    @m.call_if_not_inside(m.Attribute())
    def leave_Name(
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.BaseExpression:
        qualified_name = self._get_qualified_name(original_node)
        if (
            not qualified_name
            or qualified_name.source != cst.metadata.QualifiedNameSource.IMPORT
            or not qualified_name.name.startswith("pydantic.")
        ):
            return original_node

        for replacement in self._name_replacements:
            if replacement.matches(original_node):
                return replacement.replace(original_node)

        return original_node

    @staticmethod
    def _rename_direct_import(s: str) -> str:
        return f"PydanticV1{s}" if s[0].isupper() else f"pydantic_v1_{s}"

    def _get_qualified_name(
        self, node: cst.CSTNode
    ) -> cst.metadata.QualifiedName | None:
        qualified_names = self.get_metadata(cst.metadata.QualifiedNameProvider, node)
        if len(qualified_names) == 0:
            return None
        elif len(qualified_names) > 1:
            raise NotImplementedError
        return qualified_names.pop()


def _to_string(attribute: cst.Attribute | cst.Name) -> str:
    if isinstance(attribute, cst.Name):
        return attribute.value
    else:
        assert isinstance(attribute.value, cst.Attribute | cst.Name)
        return _to_string(attribute.value) + "." + attribute.attr.value


def _to_attribute(s: str) -> cst.Attribute | cst.Name:
    if "." in s:
        left, right = s.rsplit(".", maxsplit=1)
        return cst.Attribute(value=_to_attribute(left), attr=cst.Name(value=right))
    return cst.Name(value=s)


@functools.cache
def _is_module(s: str) -> bool:
    try:
        importlib.import_module(s)
    except ModuleNotFoundError:
        logging.debug(f"{s} is not a module")
        return False
    except Exception as e:
        logging.debug(f"{s} is a module (error: {e})")
        return True
    else:
        logging.debug(f"{s} is a module")
        return True
