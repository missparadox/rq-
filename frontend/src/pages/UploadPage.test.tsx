import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { afterEach } from "vitest";
import { vi } from "vitest";

import { UploadPage } from "./UploadPage";


function EvaluationDestination() {
  const { evaluationId } = useParams();

  return <p>evaluation destination: {evaluationId}</p>;
}


afterEach(() => {
  vi.unstubAllGlobals();
});

test("submitting a selected file posts an evaluation request", async () => {
  const file = new File(["OR需求编号,OR需求名称*,OR需求描述*\nD1,N,D\n"], "requirements.csv", {
    type: "text/csv",
  });
  let resolveRequest!: (value: {
    evaluation_id: string;
    status: string;
    filename: string;
    dedupe_hit: boolean;
    created_at: string;
  }) => void;
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () =>
      new Promise((resolve) => {
        resolveRequest = resolve;
      }),
  });
  vi.stubGlobal("fetch", fetchMock);

  render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/evaluations/:evaluationId" element={<EvaluationDestination />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(screen.getByRole("heading", { name: "需求评估平台" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "需求评估平台" })).toHaveClass("page-title");
  expect(screen.getByText("Requirements Evaluation Suite")).toBeInTheDocument();
  expect(screen.getByText("阶段 01")).toBeInTheDocument();
  expect(screen.getByText("阶段 02")).toBeInTheDocument();
  expect(screen.getByText("阶段 03")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "提交需求文档" })).toBeInTheDocument();
  expect(screen.getByText("支持 CSV、Excel 与 JSON 格式。文件提交后，平台将立即创建评估任务并启动处理流程。")).toBeInTheDocument();
  expect(screen.queryByText("将正式版本需求文件作为唯一输入提交。平台会创建评估任务，并在结果页持续反馈处理进展与最终结论。")).not.toBeInTheDocument();
  expect(screen.getByText("评估文件上传")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "选择文件" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "开始评估" })).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("评估文件上传"), {
    target: { files: [file] },
  });
  const submitButton = screen.getByRole("button", { name: "开始评估" });
  const form = submitButton.closest("form");

  if (!form) {
    throw new Error("Expected upload form to be present.");
  }

  await act(async () => {
    fireEvent.submit(form);
    fireEvent.submit(form);
  });

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "提交中..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "选择文件" })).toBeDisabled();
    expect(screen.getByLabelText("评估文件上传")).toBeDisabled();
  });

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/evaluations",
      expect.objectContaining({
        method: "POST",
        body: expect.any(FormData),
      }),
    );
  });

  resolveRequest({
    evaluation_id: "eval_123",
    status: "pending",
    filename: "requirements.csv",
    dedupe_hit: false,
    created_at: "2026-04-05T00:00:00Z",
  });

  expect(await screen.findByText("evaluation destination: eval_123")).toBeInTheDocument();
});

test("failed submission unlocks the form and allows retry", async () => {
  const file = new File(["OR需求编号,OR需求名称*,OR需求描述*\nD1,N,D\n"], "requirements.csv", {
    type: "text/csv",
  });
  const fetchMock = vi
    .fn()
    .mockRejectedValueOnce(new Error("network error"))
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        evaluation_id: "eval_retry",
        status: "pending",
        filename: "requirements.csv",
        dedupe_hit: false,
        created_at: "2026-04-05T00:00:00Z",
      }),
    });
  vi.stubGlobal("fetch", fetchMock);

  render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/evaluations/:evaluationId" element={<EvaluationDestination />} />
      </Routes>
    </MemoryRouter>,
  );

  fireEvent.change(screen.getByLabelText("评估文件上传"), {
    target: { files: [file] },
  });
  fireEvent.click(screen.getByRole("button", { name: "开始评估" }));

  expect(await screen.findByText("评估提交失败，请稍后重试。")).toBeInTheDocument();

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "开始评估" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "选择文件" })).toBeEnabled();
    expect(screen.getByLabelText("评估文件上传")).toBeEnabled();
  });

  fireEvent.click(screen.getByRole("button", { name: "开始评估" }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  expect(await screen.findByText("evaluation destination: eval_retry")).toBeInTheDocument();
});
