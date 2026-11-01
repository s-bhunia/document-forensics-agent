import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AnalyzePage } from "./pages/AnalyzePage";
import { HistoryPage } from "./pages/HistoryPage";
import { AnalysisDetailPage } from "./pages/AnalysisDetailPage";
import { NotFoundPage } from "./pages/NotFoundPage";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<AnalyzePage />} />
        <Route path="analyses" element={<HistoryPage />} />
        <Route path="analyses/:id" element={<AnalysisDetailPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
