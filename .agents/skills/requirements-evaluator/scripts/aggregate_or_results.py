#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import evaluate_requirements as packet_builder


LIST_FIELDS = (
    "triggered_red_line_rules",
    "blocking_issues",
    "key_evidence",
    "red_flags",
    "missing_items",
    "revision_actions",
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate per-OR model results into one final Chinese markdown report."
    )
    parser.add_argument("--input", required=True, help="Path to the original requirement file (.xlsx, .xlsm, .json)")
    parser.add_argument(
        "--results-dir",
        help="Directory containing per-OR model outputs. Defaults to reports/<input-file-stem>/results",
    )
    parser.add_argument(
        "--output",
        help="Path to the final markdown report. Defaults to reports/<input-file-stem>/report.md",
    )
    return parser.parse_args(argv)


def write_output(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_review_packet(input_path: Path) -> Dict[str, object]:
    result = packet_builder.read_records(input_path)
    dimensions = packet_builder.build_dimensions()
    return packet_builder.build_review_packet(
        input_path=input_path,
        dimensions=dimensions,
        records=result.records,
        source_info=result.source_info,
    )


def format_number(value: float | int | None) -> str:
    if value is None:
        return "N/A"
    value_float = float(value)
    if value_float.is_integer():
        return str(int(value_float))
    return f"{value_float:.1f}"


def format_score(value: float | int | None, max_score: float | int) -> str:
    return f"{format_number(value)}/{format_number(max_score)}"


def normalize_list_value(items: Iterable[str]) -> List[str]:
    normalized = []
    for item in items:
        if isinstance(item, dict):
            text = (
                item.get("id")
                or item.get("name")
                or item.get("rule")
                or item.get("text")
                or item.get("message")
                or ""
            )
        else:
            text = item
        cleaned = packet_builder.clean_text(str(text))
        if cleaned:
            normalized.append(cleaned)
    if len(normalized) == 1 and normalized[0] in {"无", "None", "none", "N/A", "n/a"}:
        return []
    return normalized


def coerce_score(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = packet_builder.clean_text(str(value))
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))


def build_dimension_catalog() -> Dict[str, Dict[str, float]]:
    catalog = {"or": {}, "dr": {}, "cross": {}}
    for item in packet_builder.DEFAULT_DIMENSIONS:
        bucket = "cross"
        key = str(item["key"])
        if key.startswith("or_"):
            bucket = "or"
        elif key.startswith("dr_"):
            bucket = "dr"
        catalog[bucket][str(item["name"])] = float(item["weight"])
    return catalog


def extract_json_object(text: str) -> dict | None:
    candidates = [text.strip()]
    candidates.extend(match.strip() for match in re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.S))
    brace_match = re.search(r"(\{.*\})", text, flags=re.S)
    if brace_match:
        candidates.append(brace_match.group(1).strip())
    for candidate in candidates:
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def parse_tagged_text(text: str) -> dict | None:
    match = re.search(r"\[OR_RESULT_START\](.*?)\[OR_RESULT_END\]", text, flags=re.S)
    if not match:
        return None
    body = match.group(1)
    result = {
        "scalar": {},
        "lists": defaultdict(list),
        "dr_scores": {},
        "or_dimensions": [],
        "dr_dimensions": defaultdict(list),
        "cross_dimensions": [],
    }
    current_list: str | None = None
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if current_list and (line.startswith("- ") or re.match(r"^\d+\.\s+", line)):
            item = re.sub(r"^(?:- |\d+\.\s+)", "", line).strip()
            result["lists"][current_list].append(item)
            continue
        current_list = None

        or_dimension_match = re.match(
            r"^or_dimension\.(.+?):\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*\|\s*(.+)$",
            line,
        )
        if or_dimension_match:
            result["or_dimensions"].append(
                {
                    "name": packet_builder.clean_text(or_dimension_match.group(1)),
                    "score": float(or_dimension_match.group(2)),
                    "max_score": float(or_dimension_match.group(3)),
                    "reason": packet_builder.clean_text(or_dimension_match.group(4)),
                }
            )
            continue

        dr_dimension_match = re.match(
            r"^dr_dimension\.([^.]+)\.(.+?):\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*\|\s*(.+)$",
            line,
        )
        if dr_dimension_match:
            dr_id = packet_builder.clean_text(dr_dimension_match.group(1))
            result["dr_dimensions"][dr_id].append(
                {
                    "name": packet_builder.clean_text(dr_dimension_match.group(2)),
                    "score": float(dr_dimension_match.group(3)),
                    "max_score": float(dr_dimension_match.group(4)),
                    "reason": packet_builder.clean_text(dr_dimension_match.group(5)),
                }
            )
            continue

        cross_dimension_match = re.match(
            r"^cross_dimension\.(.+?):\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*\|\s*(.+)$",
            line,
        )
        if cross_dimension_match:
            result["cross_dimensions"].append(
                {
                    "name": packet_builder.clean_text(cross_dimension_match.group(1)),
                    "score": float(cross_dimension_match.group(2)),
                    "max_score": float(cross_dimension_match.group(3)),
                    "reason": packet_builder.clean_text(cross_dimension_match.group(4)),
                }
            )
            continue

        dr_score_match = re.match(r"^dr_score\.([^.]+):\s*([0-9]+(?:\.[0-9]+)?)$", line)
        if dr_score_match:
            result["dr_scores"][packet_builder.clean_text(dr_score_match.group(1))] = float(dr_score_match.group(2))
            continue

        list_header_match = re.match(r"^([a-z_]+):\s*$", line)
        if list_header_match and list_header_match.group(1) in LIST_FIELDS:
            current_list = list_header_match.group(1)
            continue

        scalar_match = re.match(r"^([a-z_]+):\s*(.+)$", line)
        if scalar_match:
            result["scalar"][scalar_match.group(1)] = packet_builder.clean_text(scalar_match.group(2))
    return result


def normalize_dimension_entries(
    entries: Sequence[dict],
    expected: Dict[str, float],
) -> List[dict]:
    by_name = {}
    for entry in entries:
        name = packet_builder.clean_text(str(entry.get("name", "")))
        if not name:
            continue
        max_score = coerce_score(entry.get("max_score")) or expected.get(name)
        by_name[name] = {
            "name": name,
            "score": coerce_score(entry.get("score")),
            "max_score": max_score,
            "reason": packet_builder.clean_text(str(entry.get("reason", ""))) or "未提供",
        }
    normalized = []
    for name, max_score in expected.items():
        normalized.append(
            by_name.get(
                name,
                {
                    "name": name,
                    "score": None,
                    "max_score": max_score,
                    "reason": "未提供",
                },
            )
        )
    return normalized


def build_group_maps(group: dict) -> Dict[str, dict]:
    dr_map = {}
    for dr_item in group["dr_items"]:
        dr_map[str(dr_item["id"])] = dr_item
    return dr_map


def build_dr_coverage_warnings(expected_dr_ids: Sequence[str], actual_dr_ids: Sequence[str]) -> List[str]:
    warnings = []
    expected_set = set(expected_dr_ids)
    actual_set = set(actual_dr_ids)

    missing = [dr_id for dr_id in expected_dr_ids if dr_id not in actual_set]
    if missing:
        warnings.append("结果缺少以下DR评分: " + ", ".join(missing))

    extra = sorted(dr_id for dr_id in actual_set if dr_id not in expected_set)
    if extra:
        warnings.append("结果包含未出现在评审包中的DR: " + ", ".join(extra))

    duplicate_counter = Counter(actual_dr_ids)
    duplicates = [dr_id for dr_id, count in duplicate_counter.items() if count > 1]
    if duplicates:
        warnings.append("结果中存在重复DR评分: " + ", ".join(sorted(duplicates)))

    return warnings


def sum_dimension_scores(dimension_scores: Sequence[dict]) -> float | None:
    if not dimension_scores:
        return None
    scores = []
    for item in dimension_scores:
        score = item.get("score")
        if score is None:
            return None
        scores.append(float(score))
    return sum(scores)


def append_score_mismatch_warning(
    warnings: List[str],
    label: str,
    reported_score: float | None,
    computed_score: float | None,
) -> None:
    if reported_score is None or computed_score is None:
        return
    if abs(float(reported_score) - float(computed_score)) > 0.01:
        warnings.append(
            f"{label}与维度重算结果不一致: 模型给出 {format_number(reported_score)}，脚本重算 {format_number(computed_score)}"
        )


def append_grade_mismatch_warning(
    warnings: List[str],
    reported_grade: str,
    computed_grade: str,
) -> None:
    if reported_grade and computed_grade and reported_grade != computed_grade:
        warnings.append(f"等级与重算结果不一致: 模型给出 {reported_grade}，脚本重算 {computed_grade}")


def append_fallback_warning(warnings: List[str], label: str, fallback_source: str) -> None:
    message = f"{label}缺少完整维度明细，回退使用{fallback_source}。"
    if message not in warnings:
        warnings.append(message)


def choose_score(computed_score: float | None, *fallback_scores: float | None) -> float | None:
    if computed_score is not None:
        return float(computed_score)
    for fallback_score in fallback_scores:
        if fallback_score is not None:
            return float(fallback_score)
    return None


def normalize_json_result(data: dict, group: dict, catalog: Dict[str, Dict[str, float]]) -> dict:
    dr_map = build_group_maps(group)
    review_decision = data.get("review_decision", {}) if isinstance(data.get("review_decision"), dict) else {}
    expected_dr_ids = [str(dr_item["id"]) for dr_item in group["dr_items"]]
    returned_dr_items = data.get("dr_parts", []) if isinstance(data.get("dr_parts"), list) else []
    returned_dr_map = {}
    returned_dr_ids = []
    for dr_item in returned_dr_items:
        dr_id = packet_builder.clean_text(str(dr_item.get("dr_id", "")))
        if not dr_id:
            continue
        returned_dr_ids.append(dr_id)
        returned_dr_map[dr_id] = dr_item
    dr_parts = []
    for dr_id in expected_dr_ids:
        packet_dr = dr_map.get(dr_id, {})
        dr_item = returned_dr_map.get(dr_id, {})
        dr_parts.append(
            {
                "dr_id": dr_id,
                "dr_name": packet_builder.clean_text(str(dr_item.get("dr_name") or packet_dr.get("name") or dr_id)),
                "score": coerce_score(dr_item.get("score")),
                "dimension_scores": normalize_dimension_entries(
                    dr_item.get("dimension_scores", []) if isinstance(dr_item.get("dimension_scores"), list) else [],
                    catalog["dr"],
                ),
            }
        )

    return {
        "or_id": packet_builder.clean_text(str(data.get("or_id") or group["id"])),
        "or_name": packet_builder.clean_text(str(data.get("or_name") or group["name"])),
        "or_total_score": None,
        "grade": "",
        "review_conclusion": packet_builder.clean_text(str(data.get("review_conclusion", ""))),
        "or_part": {
            "score": coerce_score(
                (data.get("or_part") or {}).get("score") if isinstance(data.get("or_part"), dict) else None
            ),
            "dimension_scores": normalize_dimension_entries(
                (data.get("or_part") or {}).get("dimension_scores", [])
                if isinstance(data.get("or_part"), dict)
                else [],
                catalog["or"],
            ),
        },
        "dr_parts": dr_parts,
        "dr_average": {"score": None},
        "decomposition_quality": {
            "score": coerce_score(
                (data.get("decomposition_quality") or {}).get("score")
                if isinstance(data.get("decomposition_quality"), dict)
                else None
            ),
            "dimension_scores": normalize_dimension_entries(
                (data.get("decomposition_quality") or {}).get("dimension_scores", [])
                if isinstance(data.get("decomposition_quality"), dict)
                else [],
                catalog["cross"],
            ),
        },
        "review_decision": {
            "design_review_readiness": packet_builder.clean_text(
                str(review_decision.get("design_review_readiness") or data.get("design_review_readiness") or "")
            ),
            "development_readiness": packet_builder.clean_text(
                str(review_decision.get("development_readiness") or data.get("development_readiness") or "")
            ),
            "test_design_readiness": packet_builder.clean_text(
                str(review_decision.get("test_design_readiness") or data.get("test_design_readiness") or "")
            ),
            "blocking_issues": normalize_list_value(
                review_decision.get("blocking_issues", []) or data.get("blocking_issues", [])
            ),
        },
        "triggered_red_line_rules": normalize_list_value(
            data.get("triggered_red_line_rules", []) or review_decision.get("triggered_red_line_rules", [])
        ),
        "key_evidence": normalize_list_value(data.get("key_evidence", [])),
        "red_flags": normalize_list_value(data.get("red_flags", [])),
        "missing_items": normalize_list_value(data.get("missing_items", [])),
        "revision_actions": normalize_list_value(data.get("revision_actions", [])),
        "result_warnings": build_dr_coverage_warnings(expected_dr_ids, returned_dr_ids),
        "reported_scores": {
            "or_total_score": coerce_score(data.get("or_total_score")),
            "or_part_score": coerce_score(
                data.get("or_part_score")
                if data.get("or_part_score") is not None
                else (data.get("or_part") or {}).get("score")
            ),
            "dr_average_score": coerce_score(
                data.get("dr_average_score")
                if data.get("dr_average_score") is not None
                else (data.get("dr_average") or {}).get("score")
            ),
            "decomposition_quality_score": coerce_score(
                data.get("decomposition_quality_score")
                if data.get("decomposition_quality_score") is not None
                else (data.get("decomposition_quality") or {}).get("score")
            ),
            "grade": packet_builder.clean_text(str(data.get("grade", ""))),
            "dr_part_scores": {
                dr_id: coerce_score(returned_dr_map.get(dr_id, {}).get("score")) for dr_id in returned_dr_ids
            },
        },
    }


def normalize_tagged_result(parsed: dict, group: dict, catalog: Dict[str, Dict[str, float]]) -> dict:
    scalar = parsed["scalar"]
    dr_map = build_group_maps(group)
    expected_dr_ids = list(dr_map.keys())
    actual_dr_ids = list(parsed["dr_scores"].keys())
    for dr_id in parsed["dr_dimensions"].keys():
        if dr_id not in actual_dr_ids:
            actual_dr_ids.append(dr_id)
    dr_parts = []
    for dr_id, packet_dr in dr_map.items():
        dr_parts.append(
            {
                "dr_id": dr_id,
                "dr_name": packet_builder.clean_text(str(packet_dr["name"])),
                "score": parsed["dr_scores"].get(dr_id),
                "dimension_scores": normalize_dimension_entries(parsed["dr_dimensions"].get(dr_id, []), catalog["dr"]),
            }
        )
    return {
        "or_id": packet_builder.clean_text(scalar.get("or_id") or group["id"]),
        "or_name": packet_builder.clean_text(scalar.get("or_name") or group["name"]),
        "or_total_score": None,
        "grade": "",
        "review_conclusion": packet_builder.clean_text(scalar.get("review_conclusion", "")),
        "or_part": {
            "score": None,
            "dimension_scores": normalize_dimension_entries(parsed["or_dimensions"], catalog["or"]),
        },
        "dr_parts": dr_parts,
        "dr_average": {"score": None},
        "decomposition_quality": {
            "score": None,
            "dimension_scores": normalize_dimension_entries(parsed["cross_dimensions"], catalog["cross"]),
        },
        "review_decision": {
            "design_review_readiness": packet_builder.clean_text(scalar.get("design_review_readiness", "")),
            "development_readiness": packet_builder.clean_text(scalar.get("development_readiness", "")),
            "test_design_readiness": packet_builder.clean_text(scalar.get("test_design_readiness", "")),
            "blocking_issues": normalize_list_value(parsed["lists"].get("blocking_issues", [])),
        },
        "triggered_red_line_rules": normalize_list_value(parsed["lists"].get("triggered_red_line_rules", [])),
        "key_evidence": normalize_list_value(parsed["lists"].get("key_evidence", [])),
        "red_flags": normalize_list_value(parsed["lists"].get("red_flags", [])),
        "missing_items": normalize_list_value(parsed["lists"].get("missing_items", [])),
        "revision_actions": normalize_list_value(parsed["lists"].get("revision_actions", [])),
        "result_warnings": build_dr_coverage_warnings(expected_dr_ids, actual_dr_ids),
        "reported_scores": {
            "or_total_score": coerce_score(scalar.get("or_total_score")),
            "or_part_score": coerce_score(scalar.get("or_part_score")),
            "dr_average_score": coerce_score(scalar.get("dr_average_score")),
            "decomposition_quality_score": coerce_score(scalar.get("decomposition_quality_score")),
            "grade": packet_builder.clean_text(scalar.get("grade", "")),
            "dr_part_scores": dict(parsed["dr_scores"]),
        },
    }


def recompute_aggregate_scores(result: dict) -> dict:
    reported = result.get("reported_scores", {})
    warnings = result.setdefault("result_warnings", [])

    computed_or_part_score = sum_dimension_scores(result["or_part"]["dimension_scores"])
    result["or_part"]["score"] = choose_score(
        computed_or_part_score,
        coerce_score(result["or_part"].get("score")),
        reported.get("or_part_score"),
    )
    if computed_or_part_score is None and result["or_part"]["score"] is not None:
        append_fallback_warning(warnings, "OR部分得分", "模型给出的OR总分")
    append_score_mismatch_warning(
        warnings,
        "OR部分得分",
        reported.get("or_part_score"),
        computed_or_part_score,
    )

    for dr_part in result["dr_parts"]:
        computed_dr_score = sum_dimension_scores(dr_part["dimension_scores"])
        dr_part["score"] = choose_score(
            computed_dr_score,
            coerce_score(dr_part.get("score")),
            reported.get("dr_part_scores", {}).get(dr_part["dr_id"]),
        )
        if computed_dr_score is None and dr_part["score"] is not None:
            append_fallback_warning(
                warnings,
                f"DR {dr_part['dr_id']} 总分",
                "模型给出的DR总分",
            )
        append_score_mismatch_warning(
            warnings,
            f"DR {dr_part['dr_id']} 总分",
            reported.get("dr_part_scores", {}).get(dr_part["dr_id"]),
            computed_dr_score,
        )

    dr_scores = [item["score"] for item in result["dr_parts"] if item["score"] is not None]
    result["dr_average"]["score"] = None
    if dr_scores and len(dr_scores) == len(result["dr_parts"]):
        result["dr_average"]["score"] = sum(dr_scores) / len(dr_scores)
    elif reported.get("dr_average_score") is not None:
        result["dr_average"]["score"] = float(reported["dr_average_score"])
        append_fallback_warning(warnings, "DR平均分", "模型给出的DR平均分")
    append_score_mismatch_warning(
        warnings,
        "DR平均分",
        reported.get("dr_average_score"),
        sum(dr_scores) / len(dr_scores) if dr_scores and len(dr_scores) == len(result["dr_parts"]) else None,
    )

    computed_decomposition_score = sum_dimension_scores(
        result["decomposition_quality"]["dimension_scores"]
    )
    result["decomposition_quality"]["score"] = choose_score(
        computed_decomposition_score,
        coerce_score(result["decomposition_quality"].get("score")),
        reported.get("decomposition_quality_score"),
    )
    if computed_decomposition_score is None and result["decomposition_quality"]["score"] is not None:
        append_fallback_warning(warnings, "需求分解与追踪质量得分", "模型给出的分解质量总分")
    append_score_mismatch_warning(
        warnings,
        "需求分解与追踪质量得分",
        reported.get("decomposition_quality_score"),
        computed_decomposition_score,
    )

    pieces = [
        result["or_part"]["score"],
        result["dr_average"]["score"],
        result["decomposition_quality"]["score"],
    ]
    result["or_total_score"] = None
    if all(piece is not None for piece in pieces):
        result["or_total_score"] = sum(float(piece) for piece in pieces)
    elif reported.get("or_total_score") is not None:
        result["or_total_score"] = float(reported["or_total_score"])
        append_fallback_warning(warnings, "OR总得分", "模型给出的OR总分")
    append_score_mismatch_warning(
        warnings,
        "OR总得分",
        reported.get("or_total_score"),
        sum(float(piece) for piece in pieces) if all(piece is not None for piece in pieces) else None,
    )

    result["grade"] = packet_builder.grade_from_score(result["or_total_score"]) or "未分级"
    append_grade_mismatch_warning(warnings, reported.get("grade", ""), result["grade"])
    return result


def parse_result_file(path: Path, group: dict, catalog: Dict[str, Dict[str, float]]) -> dict:
    text = path.read_text(encoding="utf-8")
    data = extract_json_object(text)
    if data is not None:
        return recompute_aggregate_scores(normalize_json_result(data, group, catalog))
    tagged = parse_tagged_text(text)
    if tagged is not None:
        return recompute_aggregate_scores(normalize_tagged_result(tagged, group, catalog))
    raise SystemExit(f"无法解析结果文件: {path}")


def load_results(results_dir: Path, review_packet: Dict[str, object]) -> List[dict]:
    catalog = build_dimension_catalog()
    group_map = {str(group["id"]): group for group in review_packet["groups"]}
    results_by_or = {}
    for path in sorted(results_dir.iterdir()):
        if path.name.startswith(".") or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        data = extract_json_object(text)
        if data is not None:
            or_id = packet_builder.clean_text(str(data.get("or_id", "")))
        else:
            tagged = parse_tagged_text(text)
            if tagged is None:
                raise SystemExit(f"无法解析结果文件: {path}")
            or_id = packet_builder.clean_text(tagged["scalar"].get("or_id", ""))
        if not or_id:
            raise SystemExit(f"结果文件缺少 or_id: {path}")
        if or_id not in group_map:
            raise SystemExit(f"结果文件中的 OR 不存在于输入文件: {or_id} ({path})")
        if or_id in results_by_or:
            raise SystemExit(f"发现重复的 OR 结果: {or_id}")
        results_by_or[or_id] = parse_result_file(path, group_map[or_id], catalog)
    missing = [str(group["id"]) for group in review_packet["groups"] if str(group["id"]) not in results_by_or]
    if missing:
        raise SystemExit("缺少以下 OR 的结果文件: " + ", ".join(missing))
    ordered = [results_by_or[str(group["id"])] for group in review_packet["groups"]]
    return ordered


def percentage(value: float | int | None, max_score: float | int | None) -> float | None:
    if value is None or not max_score:
        return None
    return float(value) / float(max_score)


def summarize_dimension_statistics(results: Sequence[dict]) -> Dict[str, dict]:
    stats = defaultdict(lambda: {"score_sum": 0.0, "max_sum": 0.0, "count": 0})
    for result in results:
        for item in result["or_part"]["dimension_scores"]:
            if item["score"] is not None and item["max_score"] is not None:
                entry = stats[item["name"]]
                entry["score_sum"] += float(item["score"])
                entry["max_sum"] += float(item["max_score"])
                entry["count"] += 1
        for dr_part in result["dr_parts"]:
            for item in dr_part["dimension_scores"]:
                if item["score"] is not None and item["max_score"] is not None:
                    entry = stats[item["name"]]
                    entry["score_sum"] += float(item["score"])
                    entry["max_sum"] += float(item["max_score"])
                    entry["count"] += 1
        for item in result["decomposition_quality"]["dimension_scores"]:
            if item["score"] is not None and item["max_score"] is not None:
                entry = stats[item["name"]]
                entry["score_sum"] += float(item["score"])
                entry["max_sum"] += float(item["max_score"])
                entry["count"] += 1
    return stats


def summarize_dimension_list(stats: Dict[str, dict], reverse: bool, limit: int = 3) -> List[str]:
    rows = []
    for name, item in stats.items():
        if not item["max_sum"]:
            continue
        ratio = item["score_sum"] / item["max_sum"]
        average_score = item["score_sum"] / item["count"]
        average_max = item["max_sum"] / item["count"]
        rows.append((ratio, name, average_score, average_max))
    rows.sort(reverse=reverse)
    summary = []
    for ratio, name, average_score, average_max in rows[:limit]:
        summary.append(f"{name}（平均 {format_number(average_score)}/{format_number(average_max)}，{ratio * 100:.1f}%）")
    return summary or ["无足够维度数据"]


def summarize_counter(items: Iterable[str], limit: int = 3) -> List[str]:
    counter = Counter(packet_builder.clean_text(item) for item in items if packet_builder.clean_text(item))
    if not counter:
        return ["无显著集中项"]
    return [f"{text}（{count}次）" for text, count in counter.most_common(limit)]


def overall_excellent_judgment(average_score: float | None) -> str:
    if average_score is None:
        return "无法判断（没有可用的OR总分）"
    if average_score >= 90:
        return f"是（整体平均分 {format_number(average_score)}/100，达到优秀门槛）"
    return f"否（整体平均分 {format_number(average_score)}/100，未达到 90 分优秀门槛）"


def render_category_table(review_packet: Dict[str, object]) -> List[str]:
    all_counts = review_packet.get("all_category_counts", {})
    total = sum(int(count) for count in all_counts.values()) or 1
    lines = [
        "| 需求分类 | OR条目数 | 占比 | 是否参与评审 |",
        "| --- | ---: | ---: | --- |",
    ]
    for category, count in all_counts.items():
        ratio = (float(count) / float(total)) * 100
        participate = "是" if packet_builder.is_scorable_or_category(category) else "否（仅功能性需求参与评分）"
        lines.append(f"| {category} | {count} | {ratio:.1f}% | {participate} |")
    return lines


def build_dr_summary(dr_part: dict, result_warnings: Sequence[str]) -> str:
    if dr_part["score"] is None:
        for warning in result_warnings:
            if dr_part["dr_id"] in warning:
                return "该DR评分结果不完整；" + warning
        return "该DR未返回有效评分结果。"

    scored_dimensions = [
        item
        for item in dr_part["dimension_scores"]
        if item["score"] is not None and item["max_score"] not in (None, 0)
    ]
    if not scored_dimensions:
        return "该DR已返回总分，但缺少可解释的维度细项。"

    ratios = [
        (
            float(item["score"]) / float(item["max_score"]),
            item["name"],
            item["reason"],
        )
        for item in scored_dimensions
    ]
    ratios.sort()
    weakest_ratio, weakest_name, weakest_reason = ratios[0]
    strongest_ratio, strongest_name, strongest_reason = ratios[-1]

    warning_text = ""
    related_warnings = [warning for warning in result_warnings if dr_part["dr_id"] in warning]
    if related_warnings:
        warning_text = "；结果完整性异常"

    if weakest_ratio <= 0.4 and strongest_ratio >= 0.75:
        return f"强项在{strongest_name}，短板在{weakest_name}；{weakest_reason}{warning_text}"
    if weakest_ratio <= 0.4:
        return f"主要短板在{weakest_name}；{weakest_reason}{warning_text}"
    if strongest_ratio >= 0.75:
        return f"整体较完整，强项在{strongest_name}；{strongest_reason}{warning_text}"
    return f"维度表现中等，最需关注{weakest_name}；{weakest_reason}{warning_text}"


def render_dimension_rows(result: dict) -> List[str]:
    rows = []
    for item in result["or_part"]["dimension_scores"]:
        rows.append(f"| {item['name']} | {format_score(item['score'], item['max_score'])} | {item['reason']} |")
    for dr_part in result["dr_parts"]:
        rows.append(
            f"| DR `{dr_part['dr_id']} {dr_part['dr_name']}` 总分 | {format_score(dr_part['score'], 40)} | {build_dr_summary(dr_part, result.get('result_warnings', []))} |"
        )
        for item in dr_part["dimension_scores"]:
            rows.append(
                f"| ├ {item['name']} | {format_score(item['score'], item['max_score'])} | {item['reason']} |"
            )
    for item in result["decomposition_quality"]["dimension_scores"]:
        rows.append(f"| {item['name']} | {format_score(item['score'], item['max_score'])} | {item['reason']} |")
    return rows


def render_list_or_none(items: Sequence[str]) -> List[str]:
    if not items:
        return ["- 无"]
    return [f"- {item}" for item in items]


def build_priority_actions(results: Sequence[dict]) -> Dict[str, List[str]]:
    buckets = {"高": Counter(), "中": Counter(), "低": Counter()}
    for result in results:
        score = float(result["or_total_score"] or 0)
        bucket = "低"
        if score < 60 or result["review_decision"]["blocking_issues"]:
            bucket = "高"
        elif score < 75:
            bucket = "中"
        for action in result["revision_actions"]:
            buckets[bucket][action] += 1
    return {
        level: [f"{item}（{count}次）" for item, count in counter.most_common(5)] or ["无"]
        for level, counter in buckets.items()
    }


def render_report(review_packet: Dict[str, object], results: Sequence[dict]) -> str:
    valid_or_scores = [float(result["or_total_score"]) for result in results if result["or_total_score"] is not None]
    average_score = sum(valid_or_scores) / len(valid_or_scores) if valid_or_scores else None
    grade_counter = Counter(result["grade"] for result in results)
    dimension_stats = summarize_dimension_statistics(results)
    all_missing_items = [item for result in results for item in result["missing_items"]]
    all_evidence = [item for result in results for item in result["key_evidence"]]
    all_blocking_issues = [item for result in results for item in result["review_decision"]["blocking_issues"]]
    all_result_warnings = [item for result in results for item in result.get("result_warnings", [])]
    priority_actions = build_priority_actions(results)
    warning_count = sum(1 for result in results if result.get("result_warnings"))

    lines = []
    lines.append("# 需求评估报告")
    lines.append("")
    lines.append("## 1. 评估概览")
    lines.append("")
    lines.append(f"- 数据源: `{review_packet['input_path']}`")
    if review_packet.get("source_info", {}).get("sheet_name"):
        lines.append(f"- sheet_name: `{review_packet['source_info']['sheet_name']}`")
    lines.append(f"- OR 条目数: {review_packet['or_count']}")
    lines.append(f"- DR 条目数: {review_packet['dr_count']}")
    lines.append("- 评分方法: 单个 OR 总分 = OR部分得分 + DR平均分 + 需求分解与追踪质量得分")
    lines.append(f"- 总体平均分: {format_number(average_score)}/100")
    lines.append("- 等级分布: " + "，".join(f"{grade}:{count}" for grade, count in grade_counter.items()))
    lines.append(f"- 是否达到优秀设计标准的总体结论: {overall_excellent_judgment(average_score)}")
    lines.append(
        f"- 结果完整性提示: {warning_count} 个OR存在DR评分覆盖异常；报告继续生成，但这些OR的DR平均分或总分可能不完整"
    )
    lines.append("")
    lines.append("### OR需求分类统计")
    lines.append("")
    lines.extend(render_category_table(review_packet))
    lines.append("")
    included = sorted(packet_builder.SCORABLE_OR_CATEGORIES)
    lines.append(f"- 纳入评分的需求分类: {', '.join(included)}")
    lines.append("- 已排除说明: 除功能性需求外，其余需求分类默认不参与评分")
    lines.append(f"- 参与评审的OR条目数: {review_packet['or_count']}")
    lines.append(f"- 参与评审的DR条目数: {review_packet['dr_count']}")
    lines.append("")
    lines.append("## 2. 总体发现")
    lines.append("")
    lines.append("- 最常见优点: " + "；".join(summarize_dimension_list(dimension_stats, reverse=True)))
    lines.append("- 最常见问题: " + "；".join(summarize_counter(all_missing_items)))
    lines.append("- 最薄弱的维度: " + "；".join(summarize_dimension_list(dimension_stats, reverse=False)))
    structural_issues = all_blocking_issues + all_result_warnings
    if not structural_issues:
        structural_issues = all_missing_items
    lines.append("- 最值得优先修补的结构性问题: " + "；".join(summarize_counter(structural_issues)))
    lines.append("- 证据密度较高的写法信号: " + "；".join(summarize_counter(all_evidence)))
    lines.append("")
    lines.append("## 3. 单个 OR 评估结果")
    lines.append("")
    for index, result in enumerate(results, start=1):
        lines.append(f"### OR {index}: {result['or_id']} {result['or_name']}")
        lines.append("")
        lines.append(f"- OR总得分: {format_score(result['or_total_score'], 100)}")
        lines.append(f"- 等级: {result['grade']}")
        lines.append(f"- 评审结论: {result['review_conclusion'] or '未提供'}")
        lines.append(f"- OR部分得分: {format_score(result['or_part']['score'], 40)}")
        lines.append("- DR得分:")
        for dr_part in result["dr_parts"]:
            lines.append(
                f"  - `{dr_part['dr_id']} {dr_part['dr_name']}`: {format_score(dr_part['score'], 40)}"
            )
        lines.append(f"- DR平均分: {format_score(result['dr_average']['score'], 40)}")
        lines.append(
            f"- 需求分解与追踪质量得分: {format_score(result['decomposition_quality']['score'], 20)}"
        )
        lines.append("")
        lines.append("| 部分/维度 | 分数 | 说明 |")
        lines.append("| --- | ---: | --- |")
        lines.extend(render_dimension_rows(result))
        lines.append("")
        lines.append("关键证据：")
        lines.extend(render_list_or_none(result["key_evidence"]))
        lines.append("")
        lines.append("扣分依据：")
        lines.extend(render_list_or_none(result["triggered_red_line_rules"]))
        lines.append("")
        lines.append("结果完整性提示：")
        lines.extend(render_list_or_none(result.get("result_warnings", [])))
        lines.append("")
        lines.append("阻塞项：")
        lines.extend(render_list_or_none(result["review_decision"]["blocking_issues"]))
        lines.append("")
        lines.append("缺失项：")
        lines.extend(render_list_or_none(result["missing_items"]))
        lines.append("")
        lines.append("修改建议：")
        if result["revision_actions"]:
            for action_index, action in enumerate(result["revision_actions"], start=1):
                lines.append(f"{action_index}. {action}")
        else:
            lines.append("1. 无")
        lines.append("")
    lines.append("## 4. 优先级建议")
    lines.append("")
    lines.append("高优先级：")
    for item in priority_actions["高"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("中优先级：")
    for item in priority_actions["中"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("低优先级：")
    for item in priority_actions["低"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 5. 附录")
    lines.append("")
    lines.append("- 维度定义摘要:")
    for item in packet_builder.DEFAULT_DIMENSIONS:
        lines.append(f"  - {item['name']} ({item['weight']}): {item['description']}")
    lines.append("- 评分边界说明:")
    for band in packet_builder.GRADING_BANDS:
        lines.append(f"  - {band['grade']}: {band['min_score']}-{band['max_score']}")
    lines.append("- 分数计算说明:")
    lines.append("  - 单个 OR 总分 = OR部分得分 + DR平均分 + 需求分解与追踪质量得分")
    lines.append("  - DR平均分 = 同一 OR 下所有 DR 得分的算术平均值")
    lines.append("  - 整体报告总分 = 所有 OR 总得分的算术平均值")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    input_path = Path(args.input)
    artifact_dir = packet_builder.build_artifact_dir(input_path)
    results_dir = Path(args.results_dir) if args.results_dir else artifact_dir / "results"
    output_path = Path(args.output) if args.output else artifact_dir / "report.md"

    review_packet = build_review_packet(input_path)
    results = load_results(results_dir, review_packet)
    report = render_report(review_packet, results)
    write_output(output_path, report)


if __name__ == "__main__":
    main()
