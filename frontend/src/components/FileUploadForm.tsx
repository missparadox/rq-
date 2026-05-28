import { FormEvent, type ChangeEvent, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createEvaluation } from "../features/evaluations/api";

export function FileUploadForm() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  // Close the same-tick double-submit window before React applies disabled state.
  const submitLockRef = useRef(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedFile || submitLockRef.current) {
      if (!selectedFile) {
        setError("请选择待评估文件。");
      }
      return;
    }

    submitLockRef.current = true;
    setError(null);
    setIsSubmitting(true);

    try {
      const result = await createEvaluation(selectedFile);
      navigate(`/evaluations/${result.evaluation_id}`);
    } catch {
      setError("评估提交失败，请稍后重试。");
    } finally {
      submitLockRef.current = false;
      setIsSubmitting(false);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    if (isSubmitting) {
      return;
    }
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    setError(null);
  }

  function handleChooseFile() {
    if (isSubmitting) {
      return;
    }
    inputRef.current?.click();
  }

  return (
    <form className="upload-form" onSubmit={handleSubmit}>
      <div className="upload-form-heading">
        <p className="upload-section-label">评估文件上传</p>
        <h2 className="upload-form-title">提交需求文档</h2>
      </div>
      <div className="upload-file-row">
        <div className="upload-file-name">{selectedFile?.name ?? "请选择待评估文件"}</div>
        <button
          className="upload-secondary-button"
          type="button"
          onClick={handleChooseFile}
          disabled={isSubmitting}
        >
          选择文件
        </button>
        <input
          ref={inputRef}
          aria-label="评估文件上传"
          id="requirements-file"
          name="file"
          type="file"
          disabled={isSubmitting}
          onChange={handleFileChange}
        />
      </div>
      <p className="upload-help">
        支持 CSV、Excel 与 JSON 格式。文件提交后，平台将立即创建评估任务并启动处理流程。
      </p>
      <div className="upload-submit-row">
        <button className="upload-primary-button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "提交中..." : "开始评估"}
        </button>
      </div>
      {error ? <p className="upload-error">{error}</p> : null}
    </form>
  );
}
