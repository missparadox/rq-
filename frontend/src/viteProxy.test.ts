// @vitest-environment node
import config from "../vite.config";


test("dev server proxies api requests to the backend service", () => {
  expect(config.server?.proxy?.["/api"]).toEqual({
    target: "http://127.0.0.1:8000",
    changeOrigin: true,
  });
});
