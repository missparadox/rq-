#!/usr/bin/env python3
from __future__ import annotations

# Explicit external-runtime runner.
# This script is not the default standalone conversational skill path.
# It selects a repository-configured model runtime and may consult backend
# environment configuration such as API-key based providers or local CLI runtimes.

import argparse
import shutil
import sys
from pathlib import Path
from typing import Sequence

from app.core.paths import (
    DEFAULT_RUBRIC_FILE,
    REPORT_TEMPLATE_FILE,
    SKILL_SCRIPTS_ROOT,
)

if str(SKILL_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS_ROOT))

import aggregate_or_results as aggregator
import evaluate_requirements as packet_builder


FULL_REVIEW_INSTRUCTIONS = (
    "You are a requirements evaluation assistant. "
    "Evaluate the input as one full review packet and produce the final answer in Chinese Markdown. "
    "Follow the evaluation standard and report template exactly."
)

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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the external-runtime requirement evaluation workflow end-to-end in full-packet "
            "or split-per-OR mode. This script is for explicit scripted model execution, not "
            "for the default standalone conversational skill path."
        )
    )
    parser.add_argument("--input", required=True, help="Path to the requirement input file (.xlsx, .xlsm, .json)")
    parser.add_argument(
        "--review-mode",
        choices=("full", "split"),
        default="split",
        help="Use one full packet for one final report, or split into one OR packet per model call and aggregate.",
    )
    parser.add_argument(
        "--artifact-dir",
        help="Override the fixed artifact directory. Defaults to reports/<input-file-stem>/",
    )
    parser.add_argument(
        "--report-path",
        help="Override the final report path. Defaults to reports/<input-file-stem>/report-<mode>.md and syncs report.md",
    )
    parser.add_argument(
        "--packet-format",
        choices=("markdown", "json"),
        default="markdown",
        help="Format for split review packets. Result files reuse the same filename extension as packets.",
    )
    return parser.parse_args(argv)


def load_skill_assets() -> dict[str, str]:
    return {
        "standard": DEFAULT_RUBRIC_FILE.read_text(encoding="utf-8"),
        "template": REPORT_TEMPLATE_FILE.read_text(encoding="utf-8"),
    }


def render_tagged_sections(sections: Sequence[tuple[str, str]]) -> str:
    parts = []
    for name, text in sections:
        parts.append(f"[{name}]")
        parts.append(text)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def build_review_packet_data(input_path: Path) -> dict:
    result = packet_builder.read_records(input_path)
    dimensions = packet_builder.build_dimensions()
    return packet_builder.build_review_packet(
        input_path=input_path,
        dimensions=dimensions,
        records=result.records,
        source_info=result.source_info,
    )


def build_full_prompt(*, assets: dict[str, str], packet_text: str) -> str:
    return render_tagged_sections(
        (
            ("EVALUATION_STANDARD", assets["standard"]),
            ("TEMPLATE", assets["template"]),
            ("PACKET", packet_text),
        )
    )


def build_split_prompt(*, packet_text: str) -> str:
    return render_tagged_sections((("PACKET", packet_text),))


def prepare_generated_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_report_outputs(content: str, *, artifact_dir: Path, mode: str, override_path: str | None) -> Path:
    if override_path:
        target_path = Path(override_path)
    else:
        target_path = artifact_dir / f"report-{mode}.md"
    packet_builder.write_output(target_path, content)
    latest_path = artifact_dir / "report.md"
    if latest_path != target_path:
        packet_builder.write_output(latest_path, content)
    return target_path


def iter_packet_files(packets_dir: Path) -> list[Path]:
    return sorted(
        path for path in packets_dir.iterdir() if path.is_file() and path.name.startswith("or-")
    )


def run_full_mode(
    *,
    input_path: Path,
    artifact_dir: Path,
    report_path: str | None,
    model_client,
    assets: dict[str, str],
) -> Path:
    review_packet = build_review_packet_data(input_path)
    packet_text = packet_builder.render_review_packet_markdown(review_packet)
    packet_builder.write_output(artifact_dir / "full-packet.md", packet_text)
    report = model_client.generate_text(
        instructions=FULL_REVIEW_INSTRUCTIONS,
        input_text=build_full_prompt(assets=assets, packet_text=packet_text),
    )
    return write_report_outputs(report, artifact_dir=artifact_dir, mode="full", override_path=report_path)


def run_split_mode(
    *,
    input_path: Path,
    artifact_dir: Path,
    report_path: str | None,
    packet_format: str = "markdown",
    model_client,
) -> Path:
    review_packet = build_review_packet_data(input_path)
    full_packet_text = packet_builder.render_review_packet_markdown(review_packet)
    packet_builder.write_output(artifact_dir / "full-packet.md", full_packet_text)

    packet_doc = packet_builder.build_per_or_packets(review_packet)
    packets_dir = artifact_dir / "packets"
    results_dir = artifact_dir / "results"
    prepare_generated_dir(packets_dir)
    prepare_generated_dir(results_dir)
    packet_builder.write_split_packet_bundle(packets_dir, packet_doc, packet_format)

    for packet_path in iter_packet_files(packets_dir):
        packet_text = packet_path.read_text(encoding="utf-8")
        result_text = model_client.generate_text(
            instructions=SPLIT_REVIEW_INSTRUCTIONS,
            input_text=build_split_prompt(packet_text=packet_text),
        )
        packet_builder.write_output(results_dir / packet_path.name, result_text)

    results = aggregator.load_results(results_dir, review_packet)
    report = aggregator.render_report(review_packet, results)
    return write_report_outputs(report, artifact_dir=artifact_dir, mode="split", override_path=report_path)


def run_workflow(
    *,
    input_path: Path,
    review_mode: str,
    artifact_dir: Path,
    report_path: str | None,
    packet_format: str = "markdown",
    model_client,
    assets: dict[str, str] | None,
) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    if review_mode == "full":
        if assets is None:
            raise ValueError("Full review mode requires evaluation standard and template assets.")
        return run_full_mode(
            input_path=input_path,
            artifact_dir=artifact_dir,
            report_path=report_path,
            model_client=model_client,
            assets=assets,
        )
    return run_split_mode(
        input_path=input_path,
        artifact_dir=artifact_dir,
        report_path=report_path,
        packet_format=packet_format,
        model_client=model_client,
    )


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    input_path = Path(args.input)
    artifact_dir = Path(args.artifact_dir) if args.artifact_dir else packet_builder.build_artifact_dir(input_path)

    from app.clients.model_client import build_model_client, validate_model_runtime_available
    from app.core.config import get_settings

    settings = get_settings()
    validate_model_runtime_available(settings)
    model_client = build_model_client(settings)
    assets = load_skill_assets() if args.review_mode == "full" else None

    report_path = run_workflow(
        input_path=input_path,
        review_mode=args.review_mode,
        artifact_dir=artifact_dir,
        report_path=args.report_path,
        packet_format=args.packet_format,
        model_client=model_client,
        assets=assets,
    )
    print(report_path)


if __name__ == "__main__":
    main()
