import type { EvaluationDetailResponse, EvaluationStatus } from "../features/evaluations/types";

type EvaluationStatusPanelProps = {
  evaluationId?: string;
  evaluation?: EvaluationDetailResponse | null;
};

const STATUS_LABELS: Record<EvaluationStatus, string> = {
  pending: "评估准备中",
  running: "评估进行中",
  succeeded: "评估已完成",
  failed: "评估失败",
};

export function EvaluationStatusPanel({ evaluationId, evaluation }: EvaluationStatusPanelProps) {
  const currentEvaluationId = evaluation?.evaluation_id ?? evaluationId ?? "unknown";
  const statusLabel = evaluation ? STATUS_LABELS[evaluation.status] : "状态加载中";

  return (
    <section className="detail-status-panel">
      <dl className="detail-summary-grid">
        <div className="detail-summary-item">
          <dt>评估编号</dt>
          <dd>{currentEvaluationId}</dd>
        </div>
        <div className="detail-summary-item">
          <dt>文件名称</dt>
          <dd>{evaluation?.filename ?? "待获取"}</dd>
        </div>
        <div className="detail-summary-item">
          <dt>任务状态</dt>
          <dd>{statusLabel}</dd>
        </div>
      </dl>
    </section>
  );
}
