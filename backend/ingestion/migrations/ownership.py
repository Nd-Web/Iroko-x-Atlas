"""Strict schema filters, shared by migration setup and regression tests."""


def schema_of(obj):
    table = obj if hasattr(obj, "schema") else getattr(obj, "table", None)
    return getattr(table, "schema", None)


def include_object(obj, name, type_, reflected, compare_to):
    return schema_of(obj) == "ingestion" and (
        compare_to is None or schema_of(compare_to) == "ingestion"
    )


def include_name(name, type_, parents):
    return name == "ingestion" if type_ == "schema" else parents.get("schema_name") == "ingestion"
