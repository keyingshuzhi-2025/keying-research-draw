from __future__ import annotations

import argparse
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, create_model


_COMMA_SEPARATED_CONFIG_FIELDS = {
    "x", "y", "z", "u", "v", "w", "scalar", "log2fc", "pvals", "labels",
    "forest_labels", "effects", "ci_low", "ci_high", "weights", "thresholds",
    "countries", "highlight", "set_cols",
}


def _is_append_action(action: argparse.Action) -> bool:
    return action.__class__.__name__ == "_AppendAction"


def _is_boolean_flag_action(action: argparse.Action) -> bool:
    return (
        getattr(action, "nargs", None) == 0
        and isinstance(getattr(action, "const", None), bool)
        and isinstance(getattr(action, "default", None), bool)
    )


def _infer_field_type(actions: list[argparse.Action], dest: str) -> Any:
    if any(_is_append_action(a) for a in actions):
        return list[str] | str | None
    if dest in _COMMA_SEPARATED_CONFIG_FIELDS:
        return str | list[str | int | float] | None
    if actions and all(_is_boolean_flag_action(a) for a in actions):
        return bool | None

    type_candidates = {
        a.type for a in actions if getattr(a, "type", None) in {str, int, float}
    }
    if type_candidates == {int}:
        return int | None
    if type_candidates == {float}:
        return float | None
    if type_candidates == {str}:
        return str | None
    if type_candidates == {int, float}:
        return int | float | None
    return Any


def build_cli_config_model(parser: argparse.ArgumentParser) -> type[BaseModel]:
    dest_to_actions: dict[str, list[argparse.Action]] = {}
    for action in parser._actions:
        if action.dest in {"help"}:
            continue
        dest_to_actions.setdefault(action.dest, []).append(action)

    fields: dict[str, tuple[Any, Any]] = {}
    for dest, actions in dest_to_actions.items():
        fields[dest] = (_infer_field_type(actions, dest), None)

    return create_model(
        "CLIConfigModel",
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )


def validate_cli_config_payload(
    parser: argparse.ArgumentParser,
    payload: dict[str, Any],
) -> dict[str, Any]:
    model = build_cli_config_model(parser)
    try:
        validated = model.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"配置文件 schema 校验失败：\n{exc}") from exc

    result = validated.model_dump(exclude_none=True)
    for dest in _COMMA_SEPARATED_CONFIG_FIELDS:
        value = result.get(dest)
        if isinstance(value, list):
            result[dest] = ",".join(str(item) for item in value)
    # argparse append 选项统一成 list，便于后续 merge 行为一致。
    append_dests = {
        action.dest
        for action in parser._actions
        if _is_append_action(action) and action.dest in result
    }
    for dest in append_dests:
        value = result.get(dest)
        if value is None:
            continue
        if not isinstance(value, list):
            result[dest] = [str(value)]
        else:
            result[dest] = [str(item) for item in value]
    return result
