from pydantic import BaseModel


def missing_model_fields(model: BaseModel | None, fields: list[str]) -> list[str]:
    if model is None:
        return list(fields)
    result = []
    for field in fields:
        value = getattr(model, field, None)
        if value is None or value == "" or value == []:
            result.append(field)
    return result
