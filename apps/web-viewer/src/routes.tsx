import { Navigate, Route, Routes as RouterRoutes } from "react-router-dom";
import StudyListPage from "./pages/StudyListPage";
import StudyDetailPage from "./pages/StudyDetailPage";
import UploadPage from "./pages/UploadPage";
import AuditPage from "./pages/AuditPage";

export default function Routes() {
  return (
    <RouterRoutes>
      <Route path="/" element={<Navigate to="/studies" replace />} />
      <Route path="/studies" element={<StudyListPage />} />
      <Route path="/studies/:studyInstanceUid" element={<StudyDetailPage />} />
      <Route path="/upload" element={<UploadPage />} />
      <Route path="/audit" element={<AuditPage />} />
    </RouterRoutes>
  );
}
