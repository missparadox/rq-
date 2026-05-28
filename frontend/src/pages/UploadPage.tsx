import { FileUploadForm } from "../components/FileUploadForm";

export function UploadPage() {
  return (
    <main className="upload-shell">
      <div className="page-frame upload-page-frame">
        <section className="upload-panel upload-panel-premium">
          <p className="page-overline">Requirements Evaluation Suite</p>
          <h1 className="page-title">需求评估平台</h1>
          <p className="page-intro">
            为需求评审、方案治理与交付准备提供统一的质量评估入口。通过结构化分析与标准化报告输出，帮助团队更准确地识别风险、控制偏差并提升需求成熟度。
          </p>
          <div className="upload-lower">
            <section className="stage-grid" aria-label="评估阶段">
              <article className="stage-card">
                <p className="stage-label">阶段 01</p>
                <h2>提交评估文件</h2>
              </article>
              <article className="stage-card">
                <p className="stage-label">阶段 02</p>
                <h2>执行自动分析</h2>
              </article>
              <article className="stage-card">
                <p className="stage-label">阶段 03</p>
                <h2>获取评估结果</h2>
              </article>
            </section>
            <FileUploadForm />
          </div>
        </section>
      </div>
    </main>
  );
}
