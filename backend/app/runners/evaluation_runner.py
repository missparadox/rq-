from __future__ import annotations

import json
import math
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from app.core.paths import SKILL_SCRIPTS_ROOT


if str(SKILL_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS_ROOT))

import aggregate_or_results as aggregator
import evaluate_requirements as packet_builder


SPLIT_REVIEW_INSTRUCTIONS = (
    "You are a requirements evaluation assistant. "
    "Evaluate exactly one OR unit and its linked DRs. "
    "The packet is self-contained and includes the compact rubric, anchors, and red-line rules; "
    "do not require external reference documents. "
    "Return only the compact tagged-text result defined in the packet. "
    "Complete every dimension with one short evidence phrase, write a one-sentence conclusion, "
    "and limit each list to two items. "
    "Omit aggregate scores and grades because the local aggregator recomputes them. "
    "Do not output a final markdown report."
)

DEFAULT_CONTEXT_WINDOW_TOKENS = 128000
DEFAULT_RESERVED_OUTPUT_TOKENS = 4000
SOFT_LIMIT_RATIO = 0.70
HARD_LIMIT_RATIO = 0.85


def render_tagged_sections(sections: Sequence[tuple[str, str]]) -> str:
    parts = []
    for name, text in sections:
        parts.append(f"[{name}]")
        parts.append(text)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def estimate_tokens(text: str) -> int:
    char_based = math.ceil(len(text) / 1.8)
    byte_based = math.ceil(len(text.encode("utf-8")) / 4)
    return max(1, char_based, byte_based)


def build_split_prompt(*, packet_text: str) -> str:
    return render_tagged_sections((("PACKET", packet_text),))


def parse_packet_identity(packet_text: str, packet_name: str) -> dict[str, object]:
    or_id_match = re.search(r"- OR编号: `([^`]+)`", packet_text)
    or_name_match = re.search(r"- OR名称: `([^`]+)`", packet_text)
    dr_count = len(re.findall(r"^### DR ", packet_text, flags=re.M))
    return {
        "packet_name": packet_name,
        "or_id": or_id_match.group(1) if or_id_match else packet_name,
        "or_name": or_name_match.group(1) if or_name_match else packet_name,
        "dr_count": dr_count,
    }


def classify_budget_status(estimated_total_tokens: int, *, soft_limit_tokens: int, hard_limit_tokens: int) -> str:
    if estimated_total_tokens > hard_limit_tokens:
        return "oversize"
    if estimated_total_tokens > soft_limit_tokens:
        return "warning"
    return "ok"


def build_recommended_action(*, status: str, dr_count: int) -> str:
    if status == "oversize" and dr_count > 1:
        return "secondary_split_by_dr"
    if status == "oversize":
        return "compress_static_prompt_or_raise_context_window"
    if status == "warning":
        return "review_packet_size_and_trim_prompt"
    return "none"


def summarize_token_budget(budget: dict[str, object]) -> dict[str, object]:
    packets = budget["packets"]
    oversize_packets = [item for item in packets if item["budget_status"] == "oversize"]
    warning_packets = [item for item in packets if item["budget_status"] == "warning"]
    max_prompt_tokens = max((item["estimated_prompt_tokens"] for item in packets), default=0)
    max_total_tokens = max((item["estimated_total_tokens"] for item in packets), default=0)
    summary_warnings = []
    if oversize_packets:
        summary_warnings.append(
            "发现超大OR分片: " + ", ".join(str(item["or_id"]) for item in oversize_packets[:10])
        )
    if warning_packets:
        summary_warnings.append(
            "发现接近上下文预算上限的OR分片: " + ", ".join(str(item["or_id"]) for item in warning_packets[:10])
        )
    return {
        "packet_count": len(packets),
        "oversize_packet_count": len(oversize_packets),
        "warning_packet_count": len(warning_packets),
        "max_estimated_prompt_tokens": max_prompt_tokens,
        "max_estimated_total_tokens": max_total_tokens,
        "oversize_or_ids": [item["or_id"] for item in oversize_packets],
        "warning_or_ids": [item["or_id"] for item in warning_packets],
        "warnings": summary_warnings,
    }


def build_initial_token_budget(
    *,
    packets_dir: Path,
) -> dict[str, object]:
    static_prompt_tokens = estimate_tokens(SPLIT_REVIEW_INSTRUCTIONS)
    soft_limit_tokens = math.floor(DEFAULT_CONTEXT_WINDOW_TOKENS * SOFT_LIMIT_RATIO)
    hard_limit_tokens = math.floor(DEFAULT_CONTEXT_WINDOW_TOKENS * HARD_LIMIT_RATIO)

    packets = []
    for packet_path in iter_packet_files(packets_dir):
        packet_text = packet_path.read_text(encoding="utf-8")
        packet_tokens = estimate_tokens(packet_text)
        estimated_prompt_tokens = static_prompt_tokens + packet_tokens
        estimated_total_tokens = estimated_prompt_tokens + DEFAULT_RESERVED_OUTPUT_TOKENS
        packet_identity = parse_packet_identity(packet_text, packet_path.name)
        status = classify_budget_status(
            estimated_total_tokens,
            soft_limit_tokens=soft_limit_tokens,
            hard_limit_tokens=hard_limit_tokens,
        )
        packets.append(
            {
                **packet_identity,
                "packet_chars": len(packet_text),
                "packet_bytes": len(packet_text.encode("utf-8")),
                "packet_estimated_tokens": packet_tokens,
                "estimated_prompt_tokens": estimated_prompt_tokens,
                "estimated_total_tokens": estimated_total_tokens,
                "estimated_output_tokens": None,
                "budget_status": status,
                "needs_secondary_split": status == "oversize",
                "recommended_action": build_recommended_action(status=status, dr_count=int(packet_identity["dr_count"])),
            }
        )

    budget = {
        "estimation_method": "conservative_max(chars/1.8, bytes/4)",
        "limits": {
            "context_window_tokens": DEFAULT_CONTEXT_WINDOW_TOKENS,
            "reserved_output_tokens": DEFAULT_RESERVED_OUTPUT_TOKENS,
            "soft_limit_tokens": soft_limit_tokens,
            "hard_limit_tokens": hard_limit_tokens,
        },
        "static_prompt": {
            "estimated_tokens": static_prompt_tokens,
        },
        "packets": packets,
    }
    budget["summary"] = summarize_token_budget(budget)
    return budget


def update_budget_with_result(token_budget: dict[str, object], packet_name: str, result_text: str) -> None:
    for packet in token_budget["packets"]:
        if packet["packet_name"] != packet_name:
            continue
        packet["result_chars"] = len(result_text)
        packet["result_bytes"] = len(result_text.encode("utf-8"))
        packet["estimated_output_tokens"] = estimate_tokens(result_text)
        break
    token_budget["summary"] = summarize_token_budget(token_budget)


def write_token_budget_artifact(artifact_path: Path, token_budget: dict[str, object]) -> None:
    artifact_path.write_text(json.dumps(token_budget, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_generated_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def ensure_generated_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def iter_packet_files(packets_dir: Path) -> list[Path]:
    return sorted(
        path for path in packets_dir.iterdir() if path.is_file() and path.name.startswith("or-") and path.suffix == ".md"
    )


def result_path_for_packet(results_dir: Path, packet_path: Path) -> Path:
    return results_dir / packet_path.name


def has_reusable_result(result_path: Path) -> bool:
    return result_path.exists() and bool(result_path.read_text(encoding="utf-8").strip())


def build_split_review_artifacts(*, input_path: Path, artifact_dir: Path) -> dict:
    result = packet_builder.read_records(input_path)
    dimensions = packet_builder.build_dimensions()
    review_packet = packet_builder.build_review_packet(
        input_path=input_path,
        dimensions=dimensions,
        records=result.records,
        source_info=result.source_info,
    )
    packet_doc = packet_builder.build_per_or_packets(review_packet)
    packets_dir = artifact_dir / "packets"
    results_dir = artifact_dir / "results"
    prepare_generated_dir(packets_dir)
    ensure_generated_dir(results_dir)
    packet_builder.write_split_packet_bundle(packets_dir, packet_doc, "markdown")
    return {
        "review_packet": review_packet,
        "packets_dir": packets_dir,
        "results_dir": results_dir,
    }


def hydrate_budget_from_existing_results(*, token_budget: dict[str, object], packets_dir: Path, results_dir: Path) -> None:
    for packet_path in iter_packet_files(packets_dir):
        result_path = result_path_for_packet(results_dir, packet_path)
        if not has_reusable_result(result_path):
            continue
        update_budget_with_result(
            token_budget,
            packet_path.name,
            result_path.read_text(encoding="utf-8"),
        )


class EvaluationRunner:
    def __init__(self, *, store, model_client) -> None:
        self.store = store
        self.model_client = model_client

    def run(self, evaluation_id: str) -> None:
        metadata = self.store.update_metadata(
            evaluation_id,
            {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()},
        )
        try:
            directory = self.store.evaluation_dir(evaluation_id)
            input_path = directory / metadata["filename"]
            artifacts = build_split_review_artifacts(input_path=input_path, artifact_dir=directory)
            review_packet = artifacts["review_packet"]
            packets_dir = artifacts["packets_dir"]
            results_dir = artifacts["results_dir"]
            token_budget_path = directory / "token-budget.json"
            token_budget = build_initial_token_budget(
                packets_dir=packets_dir,
            )
            hydrate_budget_from_existing_results(
                token_budget=token_budget,
                packets_dir=packets_dir,
                results_dir=results_dir,
            )
            write_token_budget_artifact(token_budget_path, token_budget)
            self.store.update_metadata(
                evaluation_id,
                {
                    "token_budget_path": str(token_budget_path),
                    "token_budget_summary": token_budget["summary"],
                },
            )

            for packet_path in iter_packet_files(packets_dir):
                result_path = result_path_for_packet(results_dir, packet_path)
                if has_reusable_result(result_path):
                    continue
                packet_text = packet_path.read_text(encoding="utf-8")
                result_text = self.model_client.generate_text(
                    instructions=SPLIT_REVIEW_INSTRUCTIONS,
                    input_text=build_split_prompt(packet_text=packet_text),
                )
                packet_builder.write_output(result_path, result_text)
                update_budget_with_result(token_budget, packet_path.name, result_text)
                write_token_budget_artifact(token_budget_path, token_budget)
                self.store.update_metadata(
                    evaluation_id,
                    {
                        "token_budget_path": str(token_budget_path),
                        "token_budget_summary": token_budget["summary"],
                    },
                )

            results = aggregator.load_results(results_dir, review_packet)
            report = aggregator.render_report(review_packet, results)
            report_path = directory / "report.md"
            report_path.write_text(report, encoding="utf-8")
            self.store.update_metadata(
                evaluation_id,
                {
                    "status": "succeeded",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "report_path": str(report_path),
                    "token_budget_path": str(token_budget_path),
                    "token_budget_summary": token_budget["summary"],
                },
            )
        except Exception as exc:
            self.store.update_metadata(
                evaluation_id,
                {
                    "status": "failed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "error_message": str(exc),
                },
            )
            raise
