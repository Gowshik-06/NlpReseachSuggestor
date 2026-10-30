import { Navigate, Route, Routes } from "react-router-dom";
import MainLayout from "./layouts/MainLayout";
import HomePage from "./pages/HomePage";

export default function App() {
  return (
    <MainLayout>
      <Routes>
        {/* Main dashboard as initial page */}
        <Route path="/" element={<HomePage />} />
        <Route path="/dashboard" element={<HomePage />} />
        <Route path="/explore" element={<HomePage />} />

        {/* Stop sign-in/register flows: redirect directly to main dashboard */}
        <Route path="/login" element={<Navigate to="/" replace />} />
        <Route path="/signin" element={<Navigate to="/" replace />} />
        <Route path="/sign-in" element={<Navigate to="/" replace />} />
        <Route path="/register" element={<Navigate to="/" replace />} />
        <Route path="/auth" element={<Navigate to="/" replace />} />

        {/* Wildcard redirect to main dashboard */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </MainLayout>
  );
}
