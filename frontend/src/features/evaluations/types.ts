export type EvaluationStatus = "pending" | "running" | "succeeded" | "failed";

export type CreateEvaluationResponse = {
  evaluation_id: string;
  status: EvaluationStatus;
  filename: string;
  dedupe_hit: boolean;
  created_at: string;
};

export type EvaluationDetailResponse = {
  evaluation_id: string;
  status: EvaluationStatus;
  filename: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  report_markdown: string | null;
};
