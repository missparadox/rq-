import { createBrowserRouter } from "react-router-dom";

import { EvaluationDetailPage } from "../pages/EvaluationDetailPage";
import { UploadPage } from "../pages/UploadPage";


export const router = createBrowserRouter([
  { path: "/", element: <UploadPage /> },
  { path: "/evaluations/:evaluationId", element: <EvaluationDetailPage /> },
]);
