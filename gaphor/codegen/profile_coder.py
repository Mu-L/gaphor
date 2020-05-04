"""Parse a SysML Gaphor Model and generate a SysML data model."""

from collections import deque
from os import PathLike
from typing import Deque, Dict, List, Optional, Set, TextIO, Tuple

from gaphor import UML
from gaphor.core.modeling.elementfactory import ElementFactory
from gaphor.storage import storage
from gaphor.UML.modelinglanguage import UMLModelingLanguage

header = """# This file is generated by profile_coder.py. DO NOT EDIT!

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Callable, List, Optional

from gaphor.core.modeling.collection import collection
from gaphor.core.modeling.element import Element
from gaphor.core.modeling.properties import (
    association,
    attribute,
    derived,
    derivedunion,
    enumeration,
    redefine,
    relation_many,
    relation_one,
)
"""


def type_converter(association, enumerations: Dict = {}) -> Optional[str]:
    """Convert association types for Python data model."""

    type_value = association.typeValue
    if type_value is None:
        return None
        # raise ValueError(
        #     f"ERROR! type is not specified for property {association.name}"
        # )
    if type_value.lower() == "boolean":
        return "int"
    elif type_value.lower() in ("integer", "unlimitednatural"):
        return "int"
    elif type_value.lower() == "string":
        return "str"
    elif type_value.endswith("Kind") or type_value.endswith("Sort"):
        # e = list(filter(lambda e: e["name"] == type_value, list(enumerations.values())))[0]
        return None
    else:
        return str(type_value)


def write_class_signature(
    trees: Dict[UML.Class, List[UML.Class]],
    cls: UML.Class,
    cls_written: Set[str],
    filename: TextIO,
) -> bool:
    """Write a class signature."""

    base_classes = [cls.name for cls in trees[cls]]
    if base_classes:
        if all(cls_name in cls_written for cls_name in base_classes):
            filename.write(f"class {cls.name}(" f"{', '.join(base_classes)}):\n")
        else:
            return False
    else:
        filename.write(f"class {cls.name}:\n")
    write_attributes(cls, filename)
    return True


def write_attributes(cls: UML.Class, filename: TextIO) -> None:
    """Write attributes based on attribute type."""

    written = False
    for a in cls.attribute["not it.association"]:  # type: ignore
        type_value = type_converter(a)
        filename.write(f"    {a.name}: attribute[{type_value}]\n")
        written = True
    for a in cls.attribute["it.association"]:  # type: ignore
        if a.name and a.name != "baseClass":
            type_value = type_converter(a)
            filename.write(f"    {a.name}: relation_one[{type_value}]\n")
            written = True
    for o in cls.ownedOperation:
        filename.write(f"    {o}: operation\n")
        written = True
    if not written:
        filename.write("    pass\n\n")


def filter_uml_classes(classes: List[UML.Class],) -> List[UML.Class]:
    """Remove classes that are part of UML."""

    uml_directory: List[str] = dir(UML.uml)
    filtered_classes = [
        cls for cls in classes if cls.name and cls.name not in uml_directory
    ]
    uml_classes = [cls for cls in classes if cls.name in uml_directory]
    return uml_classes


def get_class_extensions(cls: UML.Class):
    """Get the meta classes connected with extensions."""
    for a in cls.attribute["it.association"]:  # type: ignore
        if a.name == "baseClass":
            meta_cls = a.association.ownedEnd.class_
            yield meta_cls


def create_class_trees(classes: List[UML.Class]) -> Dict[UML.Class, List[UML.Class]]:
    """Create a tree of UML.Class elements.

    The relationship between the classes is a generalization. Since the opposite
    relationship, `cls.specific` is not currently stored, only the children
    know who their parents are, the parents don't know the children.

    """
    trees = {}
    for cls in classes:
        base_classes = [base_cls for base_cls in cls.general]
        meta_classes = [meta_cls for meta_cls in get_class_extensions(cls)]
        trees[cls] = base_classes + meta_classes
    return trees


def create_referenced(classes: List[UML.Class]) -> Set[UML.Class]:
    """UML.Class elements that are referenced by others.

    We consider a UML.Class referenced when its child UML.Class has a
    generalization relationship to it.

    """
    referenced = set()
    for cls in classes:
        for gen in cls.general:
            referenced.add(gen)
        for meta_cls in get_class_extensions(cls):
            referenced.add(meta_cls)
    return referenced


def find_root_nodes(
    trees: Dict[UML.Class, List[UML.Class]], referenced: Set[UML.Class]
) -> List[UML.Class]:
    """Find the root nodes of tree models.

    The root nodes aren't generalizing other UML.Class objects, but are being
    referenced by others through their own generalizations.

    """
    return [key for key, value in trees.items() if not value and key in referenced]


def breadth_first_search(
    trees: Dict[UML.Class, List[UML.Class]], root_nodes: List[UML.Class]
) -> List[UML.Class]:
    """Perform Breadth-First Search."""

    explored: List[UML.Class] = []
    queue: Deque[UML.Class] = deque()
    for root in root_nodes:
        queue.append(root)
    while queue:
        node = queue.popleft()
        if node not in explored:
            explored.append(node)
            neighbors: List[UML.Class] = []
            for key, value in trees.items():
                if node in value:
                    neighbors.append(key)
            if neighbors:
                for neighbor in neighbors:
                    queue.append(neighbor)
    return explored


def generate(
    filename: PathLike, outfile: PathLike, overridesfile: Optional[PathLike] = None,
) -> None:
    """Generates the Python data model.

    Opens the Gaphor model, generates the list of classes using the element
    factory, and then creates a new Python data model using a relationship
    search tree.

    """
    element_factory = ElementFactory()
    modeling_language = UMLModelingLanguage()
    with open(filename):
        storage.load(
            filename, element_factory, modeling_language,
        )
    with open(outfile, "w") as f:
        f.write(header)
        classes: List = element_factory.lselect(lambda e: e.isKindOf(UML.Class))
        classes = [cls for cls in classes if cls.name[0] != "~"]

        trees = create_class_trees(classes)
        referenced = create_referenced(classes)
        root_nodes = find_root_nodes(trees, referenced)

        cls_written: Set[str] = set()
        uml_classes = filter_uml_classes(classes)
        for cls in uml_classes:
            f.write(f"from gaphor.UML import {cls.name}\n\n")
            cls_written.add(cls.name)

        classes_found: List[UML.Class] = breadth_first_search(trees, root_nodes)
        classes_deferred: List[UML.Class] = []
        for cls in classes_found:
            if cls.name not in cls_written:
                if write_class_signature(trees, cls, cls_written, f):
                    cls_written.add(cls.name)
                else:
                    classes_deferred.append(cls)

        for cls in classes_deferred:
            write_class_signature(trees, cls, cls_written, f)

    element_factory.shutdown()
