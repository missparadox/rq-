import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { EvaluationStatusPanel } from "../components/EvaluationStatusPanel";
import { ReportViewer } from "../components/ReportViewer";
import { useEvaluationDetail, useRetryEvaluation } from "../features/evaluations/hooks";
import { downloadMarkdown } from "../lib/download";

function SectionDivider({ title }: { title: string }) {
  return (
    <div className="section-divider" aria-hidden="true">
      <span className="section-divider-line" />
      <h2 className="section-divider-title">{title}</h2>
      <span className="section-divider-line" />
    </div>
  );
}

function getReportScore(markdown: string) {
  const match = markdown.match(/(?:总体评分|总分|score)\s*[:：]?\s*(\d{1,3})/i);

  return match?.[1] ?? "待解析";
}

function getReportSummary(markdown: string) {
  const lines = markdown
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith("#"));

  return lines[0] ?? "结果摘要将随报告内容展示。";
}

function getSuggestionState(score: string) {
  const numericScore = Number.parseInt(score, 10);

  if (Number.isNaN(numericScore)) {
    return "建议人工复核";
  }
  if (numericScore >= 85) {
    return "建议推进";
  }
  if (numericScore >= 70) {
    return "建议补充后推进";
  }
  return "建议暂缓";
}

function findKeywordLine(markdown: string, keywords: string[]) {
  const lines = markdown
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith("#"));

  return lines.find((line) => keywords.some((keyword) => line.includes(keyword)));
}

function WaitingStateCard({ status }: { status: "pending" | "running" }) {
  const refreshSeconds = 30;
  const [secondsRemaining, setSecondsRemaining] = useState(refreshSeconds);

  const title = status === "pending" ? "评估准备中" : "评估进行中";
  const message =
    status === "pending"
      ? "评估任务已创建，系统正在准备分析所需内容。结果将自动刷新，请稍候。"
      : "评估依赖模型处理，系统正在生成分析结果。页面将每 30 秒自动刷新，请耐心等待。";

  useEffect(() => {
    setSecondsRemaining(refreshSeconds);

    const timer = window.setInterval(() => {
      setSecondsRemaining((current) => {
        if (current <= 1) {
          return refreshSeconds;
        }

        return current - 1;
      });
    }, 1_000);

    return () => {
      window.clearInterval(timer);
    };
  }, [status]);

  return (
    <section className="state-card waiting-card" aria-live="polite">
      <div className="state-card-mark" aria-hidden="true">
        ...
      </div>
      <p className="state-card-label">状态</p>
      <h2 className="detail-card-title">{title}</h2>
      <p className="detail-copy">{message}</p>
      <div className="refresh-inline-card">
        <div className="refresh-circle">{secondsRemaining}s</div>
        <div>
          <p className="refresh-inline-title">状态刷新</p>
          <p>系统将在 {secondsRemaining} 秒后刷新最新状态</p>
        </div>
      </div>
    </section>
  );
}

function FailedStateCard({
  errorMessage,
  isRetrying,
  onRetry,
}: {
  errorMessage: string;
  isRetrying: boolean;
  onRetry: () => void;
}) {
  return (
    <section className="state-card failed-card" aria-live="polite">
      <div className="state-card-mark" aria-hidden="true">
        !
      </div>
      <p className="state-card-label">状态</p>
      <h2 className="detail-card-title">评估失败</h2>
      <p className="detail-copy failed-card-copy">
        当前评估未完成结果生成。你可以重新发起评估，或回到上传页重新提交文档。
      </p>
      <div className="error-block">
        <p className="error-block-label">异常说明</p>
        <p>{errorMessage}</p>
      </div>
      <div className="detail-card-actions">
        <button className="upload-primary-button" type="button" onClick={onRetry} disabled={isRetrying}>
          {isRetrying ? "重新发起中..." : "重新发起评估"}
        </button>
        <Link className="detail-link" to="/">
          回到上传页面
        </Link>
      </div>
    </section>
  );
}

function SucceededState({ evaluationId, markdown }: { evaluationId: string; markdown: string }) {
  const [revealPhase, setRevealPhase] = useState(1);
  const reportScore = getReportScore(markdown);
  const reportSummary = getReportSummary(markdown);
  const suggestionState = getSuggestionState(reportScore);
  const risk =
    findKeywordLine(markdown, ["风险", "问题", "缺失"]) ?? "报告中未显式列出核心风险，建议结合详细报告进行人工复核。";
  const action =
    findKeywordLine(markdown, ["建议", "动作", "改进", "补充"]) ?? "优先补充关键需求信息，并基于详细报告完成进一步修订。";
  const explanation =
    findKeywordLine(markdown, ["说明", "依据", "结论", "评分"]) ?? "本结论基于当前上传文档的结构化分析结果生成，详细依据请见完整报告。";

  useEffect(() => {
    setRevealPhase(1);
    const timers = [
      window.setTimeout(() => setRevealPhase(2), 80),
      window.setTimeout(() => setRevealPhase(3), 400),
      window.setTimeout(() => setRevealPhase(4), 700),
    ];

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [markdown]);

  return (
    <>
      <section className="result-overview-grid">
        <section className="detail-panel conclusion-hero-card">
          <div className="conclusion-hero-header">
            <div>
              <p className="eyebrow">评估结论</p>
              <h2 className="detail-card-title">评估已完成</h2>
            </div>
            <button
              className="upload-primary-button"
              type="button"
              onClick={() => downloadMarkdown(`${evaluationId}.md`, markdown)}
            >
              下载评估报告
            </button>
          </div>
          <p className="detail-copy">
            {reportSummary}
          </p>
        </section>
        <section className="result-side-cards">
          <article className="detail-panel result-metric-card">
            <p>总体评分</p>
            <strong>{reportScore}</strong>
          </article>
          <article className="detail-panel result-metric-card">
            <p>建议状态</p>
            <strong>{suggestionState}</strong>
          </article>
        </section>
      </section>
      {revealPhase >= 3 ? (
        <ReportViewer
          action={action}
          explanation={explanation}
          markdown={markdown}
          risk={risk}
          summary={reportSummary}
          showSummary={revealPhase >= 4}
        />
      ) : null}
    </>
  );
}

export function EvaluationDetailPage() {
  const { evaluationId } = useParams();
  const navigate = useNavigate();
  const evaluationDetailQuery = useEvaluationDetail(evaluationId);
  const retryEvaluationMutation = useRetryEvaluation();
  const evaluation = evaluationDetailQuery.data;
  const markdown =
    evaluation?.report_markdown ?? `# Evaluation ${evaluationId ?? "unknown"}\n\nReport pending.`;

  const renderStateCard = () => {
    if (evaluationDetailQuery.isError) {
      const errorMessage =
        evaluationDetailQuery.error instanceof Error
          ? evaluationDetailQuery.error.message
          : "评估状态获取失败，请稍后重试。";

      return (
        <FailedStateCard
          errorMessage={errorMessage}
          isRetrying={false}
          onRetry={() => navigate("/")}
        />
      );
    }

    if (!evaluation || evaluation.status === "pending") {
      return <WaitingStateCard status="pending" />;
    }

    if (evaluation.status === "running") {
      return <WaitingStateCard status="running" />;
    }

    if (evaluation.status === "failed") {
      return (
        <FailedStateCard
          errorMessage={evaluation.error_message ?? "评估执行失败，请重新发起任务。"}
          isRetrying={retryEvaluationMutation.isPending}
          onRetry={() => {
            if (!evaluation?.evaluation_id) {
              return;
            }

            retryEvaluationMutation.mutate(evaluation.evaluation_id, {
              onSuccess: (result) => {
                navigate(`/evaluations/${result.evaluation_id}`);
              },
            });
          }}
        />
      );
    }

    return <SucceededState evaluationId={evaluationId ?? "evaluation"} markdown={markdown} />;
  };

  return (
    <main className="detail-shell">
      <div className="page-frame detail-page-frame">
        <header className="detail-header">
          <p className="page-overline">Requirements Evaluation Suite</p>
          <h1 className="page-title">需求评估结果</h1>
        </header>
        <SectionDivider title="任务信息" />
        <section className="detail-page-section" aria-label="任务信息概览">
          <EvaluationStatusPanel evaluationId={evaluationId} evaluation={evaluation ?? null} />
        </section>
        <SectionDivider title="评估结论" />
        <section className="detail-page-section conclusion-stack" aria-label="结果概览">
          {renderStateCard()}
        </section>
      </div>
    </main>
  );
}
