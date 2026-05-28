import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
MODULE_PATH = SCRIPTS_DIR / "aggregate_or_results.py"


def load_module():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location("aggregate_results_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AggregateOrResultsTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_parse_tagged_text_end_to_end(self):
        rows = [
            {
                "OR需求编号": "DOR-1",
                "OR需求名称*": "网络检测与诊断",
                "OR需求描述*": "提供网络检测与维护功能。",
                "需求分类": "功能",
                "DR需求编号": "DDR-1",
                "DR需求名称*": "Ping检测",
                "DR需求描述*": "支持 Ping 检测。",
            }
        ]
        tagged_result = """[OR_RESULT_START]
or_id: DOR-1
or_name: 网络检测与诊断
or_total_score: 74
or_part_score: 28
or_dimension.OR-用户语言描述: 8/12 | 基本能看懂，但用户语言不够充分。
or_dimension.OR-应用场景: 9/12 | 有场景，但触发条件略弱。
or_dimension.OR-用户价值: 7/10 | 价值有描述，但不够量化。
or_dimension.OR-约束和限制: 4/6 | 约束较少。
dr_score.DDR-1: 30
dr_dimension.DDR-1.DR-安全分析: 3/5 | 提到安全约束，但不够细。
dr_dimension.DDR-1.DR-技术描述: 8/10 | 正常流程较清楚。
dr_dimension.DDR-1.DR-可测试性: 8/10 | 可导出主要测试点。
dr_dimension.DDR-1.DR-无歧义性: 6/8 | 参数边界较清楚。
dr_dimension.DDR-1.DR-异常描述: 5/7 | 异常路径覆盖不足。
dr_average_score: 30
decomposition_quality_score: 16
cross_dimension.需求分解完整性: 5/7 | 主能力基本覆盖。
cross_dimension.需求分解边界清晰度: 4/6 | 边界较清楚。
cross_dimension.需求映射一致性: 7/7 | OR 与 DR 基本一致。
grade: 合格
review_conclusion: 具备基础评审条件，但仍需补足异常和约束细节。
design_review_readiness: 有条件进入
development_readiness: 有条件进入
test_design_readiness: 有条件进入
triggered_red_line_rules:
- 无
blocking_issues:
- 无
key_evidence:
- OR 描述明确提到网络检测与维护。
- DR 描述中给出了 Ping 检测主流程。
red_flags:
- 异常场景没有完全展开。
missing_items:
- 约束边界不足。
revision_actions:
1. 增补失败条件与异常处理动作。
2. 明确部署约束和适用范围。
[OR_RESULT_END]
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "requirements.json"
            results_dir = tmp / "results"
            output_path = tmp / "report.md"
            input_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            results_dir.mkdir()
            (results_dir / "dor-1.txt").write_text(tagged_result, encoding="utf-8")

            self.module.main(
                [
                    "--input",
                    str(input_path),
                    "--results-dir",
                    str(results_dir),
                    "--output",
                    str(output_path),
                ]
            )

            report = output_path.read_text(encoding="utf-8")

        self.assertIn("## 1. 评估概览", report)
        self.assertIn("### OR 1: DOR-1 网络检测与诊断", report)
        self.assertIn("74/100", report)
        self.assertIn("纳入评分的需求分类: 功能", report)
        self.assertIn("约束边界不足", report)
        self.assertIn("增补失败条件与异常处理动作", report)

    def test_compact_tagged_result_recomputes_scores_without_aggregate_fields(self):
        rows = [
            {
                "OR需求编号": "DOR-1",
                "OR需求名称*": "网络检测与诊断",
                "OR需求描述*": "提供网络检测与维护功能。",
                "需求分类": "功能",
                "DR需求编号": "DDR-1",
                "DR需求名称*": "Ping检测",
                "DR需求描述*": "支持 Ping 检测。",
            }
        ]
        tagged_result = """[OR_RESULT_START]
or_id: DOR-1
or_name: 网络检测与诊断
or_dimension.OR-用户语言描述: 8/12 | 需求可识别
or_dimension.OR-应用场景: 9/12 | 场景较明确
or_dimension.OR-用户价值: 7/10 | 价值有描述
or_dimension.OR-约束和限制: 4/6 | 约束较少
dr_dimension.DDR-1.DR-安全分析: 3/5 | 安全约束较少
dr_dimension.DDR-1.DR-技术描述: 8/10 | 主流程明确
dr_dimension.DDR-1.DR-可测试性: 8/10 | 可导出测试
dr_dimension.DDR-1.DR-无歧义性: 6/8 | 边界较清楚
dr_dimension.DDR-1.DR-异常描述: 5/7 | 异常覆盖不足
cross_dimension.需求分解完整性: 5/7 | 主能力覆盖
cross_dimension.需求分解边界清晰度: 4/6 | 边界较清楚
cross_dimension.需求映射一致性: 7/7 | 映射一致
review_conclusion: 可进入评审，需补异常细节。
triggered_red_line_rules:
- 无
blocking_issues:
- 无
key_evidence:
- 主能力已有DR落点。
missing_items:
- 异常处理细节。
revision_actions:
1. 补充失败响应。
[OR_RESULT_END]
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "requirements.json"
            results_dir = tmp / "results"
            output_path = tmp / "report.md"
            input_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            results_dir.mkdir()
            (results_dir / "dor-1.txt").write_text(tagged_result, encoding="utf-8")

            self.module.main(
                [
                    "--input",
                    str(input_path),
                    "--results-dir",
                    str(results_dir),
                    "--output",
                    str(output_path),
                ]
            )
            report = output_path.read_text(encoding="utf-8")

        self.assertIn("74/100", report)
        self.assertNotIn("结果缺少以下DR", report)

    def test_parse_json_result_from_fenced_block(self):
        rows = [
            {
                "OR需求编号": "DOR-1",
                "OR需求名称*": "网络检测与诊断",
                "OR需求描述*": "提供网络检测与维护功能。",
                "需求分类": "功能",
                "DR需求编号": "DDR-1",
                "DR需求名称*": "Ping检测",
                "DR需求描述*": "支持 Ping 检测。",
            }
        ]
        json_result = {
            "or_id": "DOR-1",
            "or_name": "网络检测与诊断",
            "or_total_score": 80,
            "grade": "良好",
            "review_conclusion": "技术描述较完整，异常覆盖仍需加强。",
            "or_part": {
                "score": 30,
                "dimension_scores": [
                    {"name": "OR-用户语言描述", "score": 9, "reason": "描述清晰。"},
                    {"name": "OR-应用场景", "score": 8, "reason": "场景明确。"},
                    {"name": "OR-用户价值", "score": 8, "reason": "价值较清楚。"},
                    {"name": "OR-约束和限制", "score": 5, "reason": "约束基本齐全。"},
                ],
            },
            "dr_parts": [
                {
                    "dr_id": "DDR-1",
                    "dr_name": "Ping检测",
                    "score": 32,
                    "dimension_scores": [
                        {"name": "DR-安全分析", "score": 4, "reason": "有安全约束。"},
                        {"name": "DR-技术描述", "score": 8, "reason": "主流程清楚。"},
                        {"name": "DR-可测试性", "score": 8, "reason": "主要测试点可推导。"},
                        {"name": "DR-无歧义性", "score": 6, "reason": "边界较清晰。"},
                        {"name": "DR-异常描述", "score": 6, "reason": "异常说明尚可。"},
                    ],
                }
            ],
            "dr_average": {"score": 32},
            "decomposition_quality": {
                "score": 18,
                "dimension_scores": [
                    {"name": "需求分解完整性", "score": 6, "reason": "覆盖较完整。"},
                    {"name": "需求分解边界清晰度", "score": 6, "reason": "边界清晰。"},
                    {"name": "需求映射一致性", "score": 6, "reason": "映射一致。"},
                ],
            },
            "review_decision": {
                "design_review_readiness": "可进入",
                "development_readiness": "可进入",
                "test_design_readiness": "有条件进入",
                "blocking_issues": [],
            },
            "triggered_red_line_rules": [],
            "key_evidence": ["技术流程完整。", "测试点可以直接导出。"],
            "red_flags": ["异常恢复动作还可以更细。"],
            "missing_items": ["更明确的异常恢复说明。"],
            "revision_actions": ["补充失败恢复流程。", "细化异常输入处理。"],
        }
        wrapped = "```json\n" + json.dumps(json_result, ensure_ascii=False, indent=2) + "\n```"
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "requirements.json"
            results_dir = tmp / "results"
            output_path = tmp / "report.md"
            input_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            results_dir.mkdir()
            (results_dir / "dor-1.md").write_text(wrapped, encoding="utf-8")

            self.module.main(
                [
                    "--input",
                    str(input_path),
                    "--results-dir",
                    str(results_dir),
                    "--output",
                    str(output_path),
                ]
            )

            report = output_path.read_text(encoding="utf-8")

        self.assertIn("80/100", report)
        self.assertIn("技术描述较完整，异常覆盖仍需加强", report)
        self.assertIn("补充失败恢复流程", report)
        self.assertNotIn("DR汇总结论", report)
        self.assertIn("强项在", report)

    def test_report_falls_back_to_tagged_dr_scores_when_dr_dimensions_are_missing(self):
        rows = [
            {
                "OR需求编号": "DOR-1",
                "OR需求名称*": "网络检测与诊断",
                "OR需求描述*": "提供网络检测与维护功能。",
                "需求分类": "功能",
                "DR需求编号": "DDR-1",
                "DR需求名称*": "Ping检测",
                "DR需求描述*": "支持 Ping 检测。",
            }
        ]
        tagged_result = """[OR_RESULT_START]
or_id: DOR-1
or_name: 网络检测与诊断
or_dimension.OR-用户语言描述: 8/12 | 基本能看懂。
or_dimension.OR-应用场景: 8/12 | 场景明确。
or_dimension.OR-用户价值: 8/10 | 价值较清楚。
or_dimension.OR-约束和限制: 4/6 | 约束一般。
dr_score.DDR-1: 30
cross_dimension.需求分解完整性: 5/7 | 主能力基本覆盖。
cross_dimension.需求分解边界清晰度: 4/6 | 边界较清楚。
cross_dimension.需求映射一致性: 7/7 | OR 与 DR 基本一致。
review_conclusion: DR维度明细缺失，但总分已返回。
triggered_red_line_rules:
- 无
blocking_issues:
- 无
key_evidence:
- OR 主流程已说明。
missing_items:
- DR维度细项说明。
revision_actions:
1. 补充DR维度打分依据。
[OR_RESULT_END]
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "requirements.json"
            results_dir = tmp / "results"
            output_path = tmp / "report.md"
            input_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            results_dir.mkdir()
            (results_dir / "dor-1.txt").write_text(tagged_result, encoding="utf-8")

            self.module.main(
                [
                    "--input",
                    str(input_path),
                    "--results-dir",
                    str(results_dir),
                    "--output",
                    str(output_path),
                ]
            )

            report = output_path.read_text(encoding="utf-8")

        self.assertIn("`DDR-1 Ping检测`: 30/40", report)
        self.assertIn("- DR平均分: 30/40", report)
        self.assertIn("- OR总得分: 74/100", report)
        self.assertIn("DR DDR-1 总分缺少完整维度明细，回退使用模型给出的DR总分", report)
        self.assertIn("该DR已返回总分，但缺少可解释的维度细项", report)

    def test_report_keeps_aggregating_when_a_dr_score_is_missing(self):
        rows = [
            {
                "OR需求编号": "DOR-1",
                "OR需求名称*": "网络检测与诊断",
                "OR需求描述*": "提供网络检测与维护功能。",
                "需求分类": "功能",
                "DR需求编号": "DDR-1",
                "DR需求名称*": "Ping检测",
                "DR需求描述*": "支持 Ping 检测。",
            },
            {
                "OR需求编号": "DOR-1",
                "OR需求名称*": "网络检测与诊断",
                "OR需求描述*": "提供网络检测与维护功能。",
                "需求分类": "功能",
                "DR需求编号": "DDR-2",
                "DR需求名称*": "Telnet检测",
                "DR需求描述*": "支持 Telnet 检测。",
            },
        ]
        partial_json_result = {
            "or_id": "DOR-1",
            "or_name": "网络检测与诊断",
            "or_part": {
                "score": 30,
                "dimension_scores": [
                    {"name": "OR-用户语言描述", "score": 9, "reason": "描述清晰。"},
                    {"name": "OR-应用场景", "score": 8, "reason": "场景明确。"},
                    {"name": "OR-用户价值", "score": 8, "reason": "价值较清楚。"},
                    {"name": "OR-约束和限制", "score": 5, "reason": "约束基本齐全。"},
                ],
            },
            "dr_parts": [
                {
                    "dr_id": "DDR-1",
                    "dr_name": "Ping检测",
                    "score": 32,
                    "dimension_scores": [
                        {"name": "DR-安全分析", "score": 4, "reason": "有安全约束。"},
                        {"name": "DR-技术描述", "score": 8, "reason": "主流程清楚。"},
                        {"name": "DR-可测试性", "score": 8, "reason": "主要测试点可推导。"},
                        {"name": "DR-无歧义性", "score": 6, "reason": "边界较清晰。"},
                        {"name": "DR-异常描述", "score": 6, "reason": "异常说明尚可。"},
                    ],
                }
            ],
            "decomposition_quality": {
                "score": 18,
                "dimension_scores": [
                    {"name": "需求分解完整性", "score": 6, "reason": "覆盖较完整。"},
                    {"name": "需求分解边界清晰度", "score": 6, "reason": "边界清晰。"},
                    {"name": "需求映射一致性", "score": 6, "reason": "映射一致。"},
                ],
            },
            "review_decision": {
                "design_review_readiness": "可进入",
                "development_readiness": "可进入",
                "test_design_readiness": "有条件进入",
                "blocking_issues": [],
            },
            "triggered_red_line_rules": [],
            "key_evidence": ["技术流程完整。"],
            "red_flags": [],
            "missing_items": [],
            "revision_actions": ["补全漏掉的 DR 评分。"],
        }
        wrapped = "```json\n" + json.dumps(partial_json_result, ensure_ascii=False, indent=2) + "\n```"
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "requirements.json"
            results_dir = tmp / "results"
            output_path = tmp / "report.md"
            input_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            results_dir.mkdir()
            (results_dir / "dor-1.md").write_text(wrapped, encoding="utf-8")

            self.module.main(
                [
                    "--input",
                    str(input_path),
                    "--results-dir",
                    str(results_dir),
                    "--output",
                    str(output_path),
                ]
            )

            report = output_path.read_text(encoding="utf-8")

        self.assertIn("结果完整性提示: 1 个OR存在DR评分覆盖异常", report)
        self.assertIn("结果缺少以下DR评分: DDR-2", report)
        self.assertIn("`DDR-2 Telnet检测`: N/A/40", report)
        self.assertIn("该DR评分结果不完整", report)
        self.assertIn("总体平均分: N/A/100", report)


if __name__ == "__main__":
    unittest.main()
