"""IFC STEP metadata parser used by the browser viewer through Pyodide."""

from __future__ import annotations

import json
import re


ENTITY_RE = re.compile(r"^#(\d+)\s*=\s*(\w+)\(([^\r\n]*)\);\s*$", re.MULTILINE)
NUMBER_RE = re.compile(r"\(\s*([-+\d.Ee]+)\s*\)")
STRING_RE = re.compile(r"'((?:[^']|'')*)'")


def split_args(source: str) -> list[str]:
    result, start, depth, quoted = [], 0, 0, False
    index = 0
    while index < len(source):
        char = source[index]
        if char == "'":
            if quoted and index + 1 < len(source) and source[index + 1] == "'":
                index += 1
            else:
                quoted = not quoted
        elif not quoted:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                result.append(source[start:index].strip())
                start = index + 1
        index += 1
    result.append(source[start:].strip())
    return result


def text_value(raw: str | None) -> str:
    if not raw or raw in ("$", "*"):
        return ""
    match = STRING_RE.search(raw)
    if match:
        return match.group(1).replace("''", "'")
    return "" if raw.startswith("#") else raw.strip("'")


def number_value(raw: str | None):
    if not raw or raw in ("$", "*"):
        return None
    match = NUMBER_RE.search(raw)
    value = match.group(1) if match else raw.strip()
    try:
        result = float(value)
        return result if result == result and abs(result) != float("inf") else None
    except (TypeError, ValueError):
        return None


def references(raw: str | None) -> list[int]:
    return [int(value) for value in re.findall(r"#(\d+)", raw or "")]


def argument(args: list[str], index: int, default: str = "") -> str:
    return args[index] if 0 <= index < len(args) else default


def unit_factors(unit_lines):
    mass_factor, mass_unit = 1.0, "kg"
    length_factor, length_unit = 1.0, "m"
    mass_prefixes = {
        ".EXA.": 1e15, ".PETA.": 1e12, ".TERA.": 1e9,
        ".GIGA.": 1e6, ".MEGA.": 1e3, ".KILO.": 1.0,
        ".HECTO.": 0.1, ".DECA.": 0.01, "$": 0.001,
        ".DECI.": 0.0001, ".CENTI.": 0.00001,
        ".MILLI.": 0.000001, ".MICRO.": 1e-9, ".NANO.": 1e-12,
    }
    length_prefixes = {
        ".KILO.": 1000.0, ".HECTO.": 100.0, ".DECA.": 10.0,
        "$": 1.0, ".DECI.": 0.1, ".CENTI.": 0.01,
        ".MILLI.": 0.001, ".MICRO.": 0.000001, ".NANO.": 1e-9,
    }
    for args in unit_lines:
        if len(args) < 4:
            continue
        prefix, name = argument(args, 2), argument(args, 3)
        if argument(args, 1) == ".MASSUNIT.":
            if "GRAM" in name:
                mass_factor = mass_prefixes.get(prefix, 1.0)
                mass_unit = "kg" if mass_factor == 1 else ("g" if mass_factor < 1 else "t (kg converted)")
            elif "POUND" in name:
                mass_factor, mass_unit = 0.45359237, "lb"
        elif argument(args, 1) == ".LENGTHUNIT." and "METRE" in name:
            length_factor = length_prefixes.get(prefix, 1.0)
            length_unit = {0.001: "mm", 0.01: "cm", 1000.0: "km"}.get(length_factor, "m")
    return mass_factor, mass_unit, length_factor, length_unit


def parse_ifc_json(source: str) -> str:
    quantities, sets, products = {}, {}, {}
    property_relations, aggregate_relations, unit_lines = [], [], []
    quantity_types = {"IFCQUANTITYWEIGHT", "IFCQUANTITYLENGTH", "IFCQUANTITYAREA"}
    metadata_types = quantity_types | {"IFCPROPERTYSINGLEVALUE", "IFCELEMENTQUANTITY", "IFCPROPERTYSET", "IFCRELDEFINESBYPROPERTIES", "IFCRELAGGREGATES", "IFCSIUNIT"}
    product_excluded = quantity_types | {"IFCPROPERTYSET", "IFCELEMENTQUANTITY", "IFCPROPERTYSINGLEVALUE", "IFCSIUNIT"}
    for match in ENTITY_RE.finditer(source):
        express_id, kind = int(match.group(1)), match.group(2).upper()
        raw_args = match.group(3)
        product_candidate = not kind.startswith("IFCREL") and len(raw_args) > 2 and raw_args[0] == "'" and kind not in product_excluded
        if kind not in metadata_types and not product_candidate:
            continue
        args = split_args(raw_args)
        if kind in ("IFCQUANTITYWEIGHT", "IFCQUANTITYLENGTH", "IFCQUANTITYAREA"):
            quantity_kind = {"IFCQUANTITYWEIGHT": "weight", "IFCQUANTITYLENGTH": "length", "IFCQUANTITYAREA": "area"}[kind]
            value_index = 3
            if len(args) > value_index:
                quantities[express_id] = {"name": text_value(argument(args, 0)), "value": number_value(argument(args, value_index)), "kind": quantity_kind}
        elif kind == "IFCPROPERTYSINGLEVALUE" and len(args) > 2:
            name = text_value(argument(args, 0))
            if re.search(r"weight|length|area|profile|section|thick|size|width|height|depth|dimension|designation|shape|part.?mark|^mark$|^tag$", name, re.I):
                raw = argument(args, 2)
                value = number_value(raw)
                string_match = STRING_RE.search(raw)
                string_value = string_match.group(1).replace("''", "'") if string_match else None
                if value is not None or string_value:
                    quantity_kind = "length" if re.search("length", name, re.I) else "area" if re.search("area", name, re.I) else "weight" if re.search("weight", name, re.I) else "characteristic"
                    quantities[express_id] = {"name": name, "value": value if value is not None else string_value, "kind": quantity_kind}
        elif kind in ("IFCELEMENTQUANTITY", "IFCPROPERTYSET"):
            index = 5 if kind == "IFCELEMENTQUANTITY" else 4
            sets[express_id] = {"type": kind, "ids": references(argument(args, index))}
        elif kind == "IFCRELDEFINESBYPROPERTIES":
            property_relations.append({"products": references(argument(args, 4)), "set": next(iter(references(argument(args, 5))), None)})
        elif kind == "IFCRELAGGREGATES":
            aggregate_relations.append({"parent": next(iter(references(argument(args, 4))), None), "children": references(argument(args, 5))})
        elif kind == "IFCSIUNIT":
            unit_lines.append(args)
        elif product_candidate and len(args) >= 7:
            products[express_id] = {
                "type": kind, "guid": text_value(argument(args, 0)),
                "name": text_value(argument(args, 2)) or kind.removeprefix("IFC"),
                "objectType": text_value(argument(args, 4)),
                "tag": text_value(argument(args, 7)),
            }

    element_sets, children, parents = {}, {}, {}
    for relation in property_relations:
        if not relation["set"]:
            continue
        for express_id in relation["products"]:
            element_sets.setdefault(express_id, []).append(relation["set"])
    for relation in aggregate_relations:
        parent = relation["parent"]
        if not parent:
            continue
        children[parent] = relation["children"]
        for child in relation["children"]:
            parents.setdefault(child, set()).add(parent)

    mass_factor, mass_unit, length_factor, length_unit = unit_factors(unit_lines)

    def linked_quantities(express_id):
        for set_id in element_sets.get(express_id, []):
            prop_set = sets.get(set_id)
            if not prop_set:
                continue
            for quantity_id in prop_set["ids"]:
                quantity = quantities.get(quantity_id)
                if quantity:
                    yield prop_set, quantity

    def get_weight(express_id, type_name):
        net, generic, prop, assembly = [], [], [], []
        for prop_set, quantity in linked_quantities(express_id):
            name, value = quantity["name"], quantity["value"]
            if not isinstance(value, (int, float)):
                continue
            if prop_set["type"] == "IFCELEMENTQUANTITY":
                if re.fullmatch("netweight", name, re.I):
                    net.append(value)
                elif re.search("weight", name, re.I):
                    generic.append(value)
            elif re.fullmatch("weight", name, re.I):
                prop.append(value)
            elif re.search("assembly/cast unit weight", name, re.I):
                assembly.append(value)
        if net:
            return net[0], "NetWeight"
        if generic:
            return generic[0], "IFC quantity weight"
        if prop:
            return prop[0], "Weight property"
        if "ASSEMBLY" in type_name and assembly:
            return assembly[0], "Assembly weight"
        return None, "Not provided"

    def get_measure(express_id, measure, quantity_kind):
        quantity_values, property_values = [], []
        for prop_set, quantity in linked_quantities(express_id):
            if not isinstance(quantity["value"], (int, float)) or not re.search(measure, quantity["name"], re.I):
                continue
            if prop_set["type"] == "IFCELEMENTQUANTITY" and quantity["kind"] == quantity_kind:
                quantity_values.append(quantity["value"])
            elif prop_set["type"] == "IFCPROPERTYSET" and quantity["kind"] == quantity_kind:
                property_values.append(quantity["value"])
        if quantity_values:
            return quantity_values[0], f"IFC quantity {quantity_kind}"
        if property_values:
            return property_values[0], f"{quantity_kind.title()} property"
        return None, "Not provided"

    def get_area(express_id):
        for _, quantity in linked_quantities(express_id):
            if isinstance(quantity["value"], (int, float)) and quantity["kind"] == "area":
                return quantity["value"]
        return None

    def get_part_mark(express_id):
        for _, quantity in linked_quantities(express_id):
            if quantity["value"] is not None and re.search(r"part.?mark|^mark$|^tag$", quantity["name"], re.I):
                return str(quantity["value"])
        return ""

    def get_similarity(express_id):
        values = []
        for _, quantity in linked_quantities(express_id):
            name = quantity["name"]
            if quantity["kind"] == "characteristic" and quantity["value"] is not None and not re.search(r"part.?mark|^mark$|^tag$", name, re.I):
                values.append(f"{name}:{quantity['value']}")
        return " | ".join(sorted(values))

    def nearest_assembly(express_id, type_name):
        if "ASSEMBLY" in type_name:
            return express_id
        pending, seen = list(parents.get(express_id, set())), set()
        while pending:
            parent = pending.pop(0)
            if parent in seen:
                continue
            seen.add(parent)
            parent_type = products.get(parent, {}).get("type", "")
            if "ASSEMBLY" in parent_type:
                return parent
            pending.extend(parents.get(parent, set()))
        return None

    records = {}
    for express_id, product in products.items():
        type_name = product["type"]
        guid, name, object_type = product["guid"], product["name"], product["objectType"]
        part_mark = product["tag"] or get_part_mark(express_id) or object_type
        weight_value, weight_source = get_weight(express_id, type_name)
        length_value, length_source = get_measure(express_id, "length", "length")
        assembly_id = nearest_assembly(express_id, type_name)
        assembly_product = products.get(assembly_id, {}) if assembly_id else {}
        assembly_weight, assembly_weight_source = get_weight(assembly_id, assembly_product.get("type", "IFCELEMENTASSEMBLY")) if assembly_id else (None, "Not provided")
        records[str(express_id)] = {
            "id": express_id, "guid": guid, "name": name, "type": type_name,
            "objectType": object_type, "partMark": part_mark,
            "weight": weight_value * mass_factor if weight_value is not None else None,
            "weightSource": weight_source, "length": length_value,
            "lengthSource": length_source, "area": get_area(express_id),
            "similarData": get_similarity(express_id),
            "isAssembly": "ASSEMBLY" in type_name,
            "children": children.get(express_id, []),
            "parents": sorted(parents.get(express_id, set())),
            "assemblyId": assembly_id,
            "assemblyName": assembly_product.get("name", "Assembly") if assembly_id else "",
            "assemblyMark": assembly_product.get("tag", "") if assembly_id else "",
            "assemblyWeight": assembly_weight * mass_factor if assembly_weight is not None else None,
            "assemblyWeightSource": assembly_weight_source,
            "group": None, "visible": True,
        }

    return json.dumps({
        "records": records,
        "children": {str(key): value for key, value in children.items()},
        "massFactor": mass_factor, "massUnit": mass_unit,
        "lengthFactor": length_factor, "lengthUnit": length_unit,
    }, ensure_ascii=False, separators=(",", ":"))
