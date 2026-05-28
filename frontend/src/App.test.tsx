import { act, render, screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  window.history.replaceState({}, "", "/");
  vi.useRealTimers();
  vi.resetModules();
  vi.unstubAllGlobals();
});

test("app renders the evaluation detail route with query-backed data", async () => {
  window.history.replaceState({}, "", "/evaluations/eval_123");

  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      return new Response(
        JSON.stringify({
          evaluation_id: "eval_123",
          status: "pending",
          filename: "requirements.csv",
          created_at: "2026-04-05T09:00:00Z",
          started_at: null,
          finished_at: null,
          error_message: null,
          report_markdown: null,
        }),
        {
          status: 200,
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    }),
  );

  const { default: App } = await import("./App");

  render(<App />);

  expect(await screen.findByText("评估准备中")).toBeInTheDocument();
});

test("app polls pending evaluation detail every 30 seconds", async () => {
  vi.useFakeTimers();
  window.history.replaceState({}, "", "/evaluations/eval_123");

  const fetchMock = vi.fn(async () => {
    return new Response(
      JSON.stringify({
        evaluation_id: "eval_123",
        status: "pending",
        filename: "requirements.csv",
        created_at: "2026-04-05T09:00:00Z",
        started_at: null,
        finished_at: null,
        error_message: null,
        report_markdown: null,
      }),
      {
        status: 200,
        headers: {
          "Content-Type": "application/json",
        },
      },
    );
  });
  vi.stubGlobal("fetch", fetchMock);

  const { default: App } = await import("./App");

  render(<App />);

  await act(async () => {
    await Promise.resolve();
  });

  expect(screen.getByText("评估准备中")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(1);

  await act(async () => {
    vi.advanceTimersByTime(29_000);
    await Promise.resolve();
  });

  expect(fetchMock).toHaveBeenCalledTimes(1);

  await act(async () => {
    vi.advanceTimersByTime(1_000);
    await Promise.resolve();
  });

  expect(fetchMock).toHaveBeenCalledTimes(2);
});
