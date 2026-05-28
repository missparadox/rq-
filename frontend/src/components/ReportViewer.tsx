type ReportViewerProps = {
  risk: string;
  action: string;
  explanation: string;
  markdown: string;
  showSummary: boolean;
  summary: string;
};


export function ReportViewer({ risk, action, explanation, markdown, showSummary, summary }: ReportViewerProps) {
  return (
    <section className="report-viewer">
      <section className="detail-secondary-grid">
        <article className="detail-panel result-section-card">
          <p className="eyebrow">风险判断</p>
          <h3 className="result-section-title">核心风险</h3>
          <p className="detail-copy">{risk}</p>
        </article>
        <article className="detail-panel result-section-card">
          <p className="eyebrow">动作建议</p>
          <h3 className="result-section-title">优先动作</h3>
          <p className="detail-copy">{action}</p>
        </article>
        <article className="detail-panel result-section-card">
          <p className="eyebrow">结论说明</p>
          <h3 className="result-section-title">评估说明</h3>
          <p className="detail-copy">{explanation}</p>
        </article>
      </section>
      {showSummary ? (
        <article className="detail-panel result-summary-card">
          <p className="eyebrow">摘要结论</p>
          <h3 className="result-section-title">摘要结论</h3>
          <p className="detail-copy">{summary}</p>
        </article>
      ) : null}
      <section className="detail-panel report-panel">
        <p className="eyebrow">详细报告</p>
        <h3 className="result-section-title">详细报告</h3>
        <pre className="report-content">{markdown}</pre>
      </section>
    </section>
  );
}
