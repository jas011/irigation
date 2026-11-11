import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import DashboardLayout from "./layouts/DashboardLayout";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import Settings from "./pages/Settings";
import Login from "./pages/Login";
import Register from "./pages/Register";
import CropAnalysisPage from "./pages/CropAnalysisPage";
import MoistureAnalysisPage from "./pages/MoistureAnalysisPage";
import WeatherPage from "./pages/Weather/WeatherPage";
import ApiService from "./services/api";

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  if (!ApiService.isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        <Route
          element={
            <ProtectedRoute>
              <DashboardLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<Navigate to="/area-selection" replace />} />
          <Route path="/area-selection" element={<Dashboard />} />
          <Route path="/crop-analysis" element={<CropAnalysisPage />} />
          <Route path="/moisture-analysis" element={<MoistureAnalysisPage />} />
          <Route path="/history" element={<History />} />
          <Route path="/weather" element={<WeatherPage />} />
          <Route path="/settings" element={<Settings />} />
        </Route>

        <Route path="*" element={<Navigate to="/area-selection" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
