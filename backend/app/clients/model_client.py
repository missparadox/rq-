from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Protocol

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - exercised in environments without openai installed
    OpenAI = None

from app.core.config import Settings

REPORT_INSTRUCTIONS = (
    "You are a requirements evaluation assistant. "
    "Follow the rubric and produce the final answer in Chinese Markdown using the template."
)
CODEX_CLI_TIMEOUT_SECONDS = 300


class ModelClient(Protocol):
    def generate_text(self, *, instructions: str, input_text: str) -> str: ...

    def generate_report(self, *, skill_text: str, template_text: str, packet_text: str) -> str: ...


def _build_tagged_prompt(*, skill_text: str, template_text: str, packet_text: str) -> str:
    return (
        "[SKILL]\n"
        f"{skill_text}\n\n"
        "[TEMPLATE]\n"
        f"{template_text}\n\n"
        "[PACKET]\n"
        f"{packet_text}\n"
    )


def _is_split_review_request(instructions: str) -> bool:
    normalized = instructions.lower()
    return "exactly one or unit" in normalized or "per-or result" in normalized


def _build_mock_split_result(input_text: str) -> str:
    or_id_match = re.search(r"- OR编号: `([^`]+)`", input_text)
    or_name_match = re.search(r"- OR名称: `([^`]+)`", input_text)
    dr_matches = re.findall(r"^### DR ([^\s]+) (.+)$", input_text, flags=re.M)
    or_id = or_id_match.group(1) if or_id_match else "MOCK-OR"
    or_name = or_name_match.group(1) if or_name_match else "Mock OR"

    lines = [
        "[OR_RESULT_START]",
        f"or_id: {or_id}",
        f"or_name: {or_name}",
        "or_dimension.OR-用户语言描述: 6/12 | 用户诉求基本可识别",
        "or_dimension.OR-应用场景: 6/12 | 场景信息不完整",
        "or_dimension.OR-用户价值: 5/10 | 价值需补充",
        "or_dimension.OR-约束和限制: 3/6 | 限制信息不足",
    ]
    for dr_id, _dr_name in dr_matches:
        lines.extend(
            [
                f"dr_dimension.{dr_id}.DR-安全分析: 2/5 | 安全约束不足",
                f"dr_dimension.{dr_id}.DR-技术描述: 5/10 | 主行为部分明确",
                f"dr_dimension.{dr_id}.DR-可测试性: 5/10 | 需补验收条件",
                f"dr_dimension.{dr_id}.DR-无歧义性: 4/8 | 边界仍可多解",
                f"dr_dimension.{dr_id}.DR-异常描述: 2/7 | 缺失败处理",
            ]
        )
    lines.extend(
        [
            "cross_dimension.需求分解完整性: 4/7 | 主能力已覆盖",
            "cross_dimension.需求分解边界清晰度: 4/6 | DR边界基本明确",
            "cross_dimension.需求映射一致性: 4/7 | 映射基本一致",
            "review_conclusion: 可评审，但需补齐关键边界和异常。",
            "triggered_red_line_rules:",
            "- 无",
            "blocking_issues:",
            "- 无",
            "key_evidence:",
            "- 主能力有对应DR描述。",
            "missing_items:",
            "- 异常及约束细节。",
            "revision_actions:",
            "1. 补充异常响应与边界条件。",
            "[OR_RESULT_END]",
        ]
    )
    return "\n".join(lines)


class StaticModelClient:
    def generate_text(self, *, instructions: str, input_text: str) -> str:
        if _is_split_review_request(instructions):
            return _build_mock_split_result(input_text)
        return "# Mock Report\n\nReplace this client with the real model integration.\n"

    def generate_report(self, *, skill_text: str, template_text: str, packet_text: str) -> str:
        return self.generate_text(
            instructions=REPORT_INSTRUCTIONS,
            input_text=_build_tagged_prompt(
                skill_text=skill_text,
                template_text=template_text,
                packet_text=packet_text,
            ),
        )


@dataclass
class OpenAIModelClient:
    model_name: str
    client: OpenAI

    def generate_text(self, *, instructions: str, input_text: str) -> str:
        response = self.client.responses.create(
            model=self.model_name,
            instructions=instructions,
            input=input_text,
        )
        if not response.output_text:
            raise RuntimeError("OpenAI response did not contain output_text.")
        return response.output_text

    def generate_report(self, *, skill_text: str, template_text: str, packet_text: str) -> str:
        return self.generate_text(
            instructions=REPORT_INSTRUCTIONS,
            input_text=_build_tagged_prompt(
                skill_text=skill_text,
                template_text=template_text,
                packet_text=packet_text,
            ),
        )


@dataclass
class CodexModelClient:
    model_name: str

    def generate_text(self, *, instructions: str, input_text: str) -> str:
        prompt = f"{instructions}\n\n{input_text}"
        try:
            result = subprocess.run(
                ["codex", "exec", "--model", self.model_name, prompt],
                capture_output=True,
                text=True,
                timeout=CODEX_CLI_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Codex CLI timed out after {CODEX_CLI_TIMEOUT_SECONDS} seconds."
            ) from exc
        if result.returncode != 0:
            stderr = result.stderr.strip() or "no stderr output"
            raise RuntimeError(
                f"Codex CLI failed with exit code {result.returncode}: {stderr}"
            )

        report = result.stdout.strip()
        if not report:
            raise RuntimeError("Codex CLI returned empty stdout.")
        return report

    def generate_report(self, *, skill_text: str, template_text: str, packet_text: str) -> str:
        return self.generate_text(
            instructions=REPORT_INSTRUCTIONS,
            input_text=_build_tagged_prompt(
                skill_text=skill_text,
                template_text=template_text,
                packet_text=packet_text,
            ),
        )


@dataclass(frozen=True)
class ResolvedModelRuntime:
    provider_name: str
    model_name: str
    api_key: str | None = None
    base_url: str | None = None


NO_MODEL_PROVIDER_ERROR_MESSAGE = (
    "No model provider is available. Checked OPENAI_API_KEY, ZHIPU_API_KEY, "
    "Codex CLI availability on PATH via `codex`, and "
    "REQUIREMENTS_EVALUATOR_DEBUG_FALLBACK=1 for local debugging. "
    "The static placeholder runtime is not valid for application startup."
)


def resolve_model_runtime(settings: Settings) -> ResolvedModelRuntime:
    if settings.openai_api_key is not None:
        return ResolvedModelRuntime(
            provider_name="openai",
            model_name=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
    if settings.zhipu_api_key is not None:
        return ResolvedModelRuntime(
            provider_name="zhipu",
            model_name=settings.zhipu_model,
            api_key=settings.zhipu_api_key,
            base_url=settings.zhipu_base_url,
        )
    if shutil.which("codex") is not None:
        return ResolvedModelRuntime(
            provider_name="codex",
            model_name=settings.codex_model,
        )
    if settings.debug_fallback_enabled:
        return ResolvedModelRuntime(provider_name="debug", model_name="debug-fallback")
    return ResolvedModelRuntime(provider_name="static", model_name="static")


def validate_model_runtime_available(settings: Settings) -> ResolvedModelRuntime:
    runtime = resolve_model_runtime(settings)
    if runtime.provider_name == "static":
        raise RuntimeError(NO_MODEL_PROVIDER_ERROR_MESSAGE)
    return runtime


def model_provider_name(settings: Settings) -> str:
    return resolve_model_runtime(settings).provider_name


def build_model_client(settings: Settings) -> ModelClient:
    runtime = resolve_model_runtime(settings)
    if runtime.api_key is not None and runtime.base_url is not None:
        if OpenAI is None:
            raise RuntimeError("OpenAI Python package is required when OPENAI_API_KEY is configured.")
        return OpenAIModelClient(
            model_name=runtime.model_name,
            client=OpenAI(api_key=runtime.api_key, base_url=runtime.base_url),
        )
    if runtime.provider_name == "codex":
        return CodexModelClient(model_name=runtime.model_name)
    return StaticModelClient()
