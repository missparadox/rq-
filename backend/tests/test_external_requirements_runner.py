import json
import re
import tempfile
import unittest
from pathlib import Path

from app.runners import external_requirements_runner as runner


class FakeModelClient:
    def __init__(self):
        self.calls = []

    def generate_text(self, *, instructions: str, input_text: str) -> str:
        self.calls.append((instructions, input_text))
        if "Evaluate exactly one OR unit" not in instructions:
            return "# Full Report\n\n## 1. 评估概览\n\n- 数据源：`sample.json`\n"

        or_id_match = re.search(r"- or_id: ([^\n]+)", input_text)
        or_name_match = re.search(r"- or_name: ([^\n]+)", input_text)
        dr_id_match = re.search(r"- dr_id: ([^\n]+)", input_text)
        dr_name_match = re.search(r"- dr_name: ([^\n]+)", input_text)
        or_id = or_id_match.group(1).strip() if or_id_match else "DOR-UNKNOWN"
        or_name = or_name_match.group(1).strip() if or_name_match else or_id
        dr_id = dr_id_match.group(1).strip() if dr_id_match else "DDR-UNKNOWN"
        dr_name = dr_name_match.group(1).strip() if dr_name_match else dr_id
        return f"""[OR_RESULT_START]
or_id: {or_id}
or_name: {or_name}
or_dimension.OR-用户语言描述: 8/12 | 描述清楚。
or_dimension.OR-应用场景: 8/12 | 场景明确。
or_dimension.OR-用户价值: 6/10 | 价值基本清楚。
or_dimension.OR-约束和限制: 4/6 | 约束一般。
dr_dimension.{dr_id}.DR-安全分析: 4/5 | 有安全约束。
dr_dimension.{dr_id}.DR-技术描述: 8/10 | 主流程清楚。
dr_dimension.{dr_id}.DR-可测试性: 7/10 | 可导出测试点。
dr_dimension.{dr_id}.DR-无歧义性: 6/8 | 参数边界较清楚。
dr_dimension.{dr_id}.DR-异常描述: 5/7 | 异常覆盖一般。
cross_dimension.需求分解完整性: 5/7 | 主能力基本覆盖。
cross_dimension.需求分解边界清晰度: 4/6 | 边界较清楚。
cross_dimension.需求映射一致性: 5/7 | OR 与 DR 一致。
review_conclusion: {or_name}具备基础评审条件。
design_review_readiness: 有条件进入
development_readiness: 有条件进入
test_design_readiness: 有条件进入
triggered_red_line_rules:
- 无
blocking_issues:
- 无
key_evidence:
- OR 与 DR 主流程已明确。
red_flags:
- 异常路径仍需加强。
missing_items:
- 更明确的异常处理。
revision_actions:
1. 补充失败处理动作。
[OR_RESULT_END]
"""


class RunRequirementsEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.module = runner
        self.assets = {"standard": "standard", "template": "template"}

    def test_full_mode_writes_final_report_in_one_call(self):
        rows = [
            {
                "OR需求编号": "DOR-1",
                "OR需求名称*": "网络检测",
                "OR需求描述*": "支持网络检测。",
                "需求分类": "功能",
                "DR需求编号": "DDR-1",
                "DR需求名称*": "Ping检测",
                "DR需求描述*": "支持 Ping 检测。",
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "sample.json"
            artifact_dir = tmp / "artifacts"
            input_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            client = FakeModelClient()

            report_path = self.module.run_workflow(
                input_path=input_path,
                review_mode="full",
                artifact_dir=artifact_dir,
                report_path=None,
                model_client=client,
                assets=self.assets,
            )

            self.assertEqual(len(client.calls), 1)
            self.assertTrue((artifact_dir / "full-packet.md").exists())
            self.assertTrue((artifact_dir / "report-full.md").exists())
            self.assertTrue((artifact_dir / "report.md").exists())
            self.assertEqual(report_path, artifact_dir / "report-full.md")
            self.assertNotIn("[SKILL]", client.calls[0][1])
            self.assertIn("[EVALUATION_STANDARD]", client.calls[0][1])
            self.assertNotIn("[SCORING_ANCHORS]", client.calls[0][1])
            self.assertIn("[TEMPLATE]", client.calls[0][1])
            self.assertIn("## 1. 评估概览", report_path.read_text(encoding="utf-8"))

    def test_split_mode_scores_each_or_and_aggregates_report(self):
        rows = [
            {
                "OR需求编号": "DOR-1",
                "OR需求名称*": "网络检测",
                "OR需求描述*": "支持网络检测。",
                "需求分类": "功能",
                "DR需求编号": "DDR-1",
                "DR需求名称*": "Ping检测",
                "DR需求描述*": "支持 Ping 检测。",
            },
            {
                "OR需求编号": "DOR-2",
                "OR需求名称*": "日志审计",
                "OR需求描述*": "支持日志审计。",
                "需求分类": "功能",
                "DR需求编号": "DDR-2",
                "DR需求名称*": "日志查询",
                "DR需求描述*": "支持日志查询。",
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "sample.json"
            artifact_dir = tmp / "artifacts"
            input_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            client = FakeModelClient()

            report_path = self.module.run_workflow(
                input_path=input_path,
                review_mode="split",
                artifact_dir=artifact_dir,
                report_path=None,
                model_client=client,
                assets=self.assets,
            )

            self.assertEqual(len(client.calls), 2)
            self.assertTrue((artifact_dir / "packets" / "index.md").exists())
            self.assertTrue((artifact_dir / "results").exists())
            self.assertTrue((artifact_dir / "results" / "or-001-dor-1.md").exists())
            self.assertTrue((artifact_dir / "results" / "or-002-dor-2.md").exists())
            self.assertTrue((artifact_dir / "report-split.md").exists())
            self.assertTrue((artifact_dir / "report.md").exists())
            self.assertEqual(report_path, artifact_dir / "report-split.md")
            self.assertNotIn("[SKILL]", client.calls[0][1])
            self.assertNotIn("[SCORING_ANCHORS]", client.calls[0][1])
            self.assertIn("[PACKET]", client.calls[0][1])
            self.assertIn("## 评分与输出约束", client.calls[0][1])
            self.assertIn("仅输出下方 tagged 结果", client.calls[0][1])
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("### OR 1: DOR-1 网络检测", report)
            self.assertIn("### OR 2: DOR-2 日志审计", report)
            self.assertIn("缺失项：", report)
            self.assertNotIn("设计评审准入", report)


if __name__ == "__main__":
    unittest.main()
