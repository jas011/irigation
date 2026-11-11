import React, { useState, useEffect } from "react";
import { User, Shield, CheckCircle, AlertCircle, LogOut } from "lucide-react";
import ApiService from "../services/api";
import { useFieldContext } from "../layouts/DashboardLayout";
import { useNavigate } from "react-router-dom";

const Settings: React.FC = () => {
  const navigate = useNavigate();
  const { areaUnit, setAreaUnit } = useFieldContext();

  const [profile, setProfile] = useState<{ name: string; email: string } | null>(null);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");

  const [isLoading, setIsLoading] = useState(false);
  const [pwdError, setPwdError] = useState<string | null>(null);
  const [pwdSuccess, setPwdSuccess] = useState<string | null>(null);

  useEffect(() => {
    ApiService.getMe()
      .then((data) => setProfile(data))
      .catch((err) => console.error("Error loading user profile:", err));
  }, []);

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!oldPassword || !newPassword || !confirmNewPassword) {
      setPwdError("Please fill in all security fields.");
      return;
    }
    if (newPassword.length < 6) {
      setPwdError("New password must be at least 6 characters.");
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setPwdError("New passwords do not match.");
      return;
    }

    setIsLoading(true);
    setPwdError(null);
    setPwdSuccess(null);

    try {
      await ApiService.changePassword(oldPassword, newPassword);
      setPwdSuccess("Password updated successfully!");
      setOldPassword("");
      setNewPassword("");
      setConfirmNewPassword("");
    } catch (err: any) {
      setPwdError(err.message || "Failed to change password. Make sure old password is correct.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    ApiService.logout();
    navigate("/login");
  };

  return (
    <div className="settings-page">
      <div className="settings-page-intro">
        <div>
          <span className="settings-kicker">WORKSPACE CONTROL CENTER</span>
          <h1>Settings & preferences</h1>
          <p>Shape how AgriSense presents field intelligence, account details, and secure access.</p>
        </div>
        <div className="settings-status-chip"><CheckCircle size={15} /> Account protected</div>
      </div>

      <section className="settings-section settings-section--profile">
        <div className="settings-header">
          <div className="settings-badge settings-badge--green">
            <User size={22} />
          </div>
          <div>
            <h3 style={{ fontSize: "16px", fontWeight: 700 }}>Profile Information</h3>
            <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>Your account identity details</p>
          </div>
        </div>

        {profile ? (
          <div className="profile-grid">
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <span style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 600 }}>Full Name</span>
              <div className="info-box">{profile.name}</div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <span style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 600 }}>Email Address</span>
              <div className="info-box">{profile.email}</div>
            </div>
          </div>
        ) : (
          <p style={{ fontSize: "14px", color: "var(--text-muted)" }}>Loading profile information...</p>
        )}
      </section>

      <section className="settings-section settings-section--preferences">
        <h3 style={{ fontSize: "16px", fontWeight: 700, marginBottom: "4px" }}>Regional Preferences</h3>
        <p style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "20px" }}>
          Configure metric definitions for calculations
        </p>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <span style={{ fontSize: "14px", fontWeight: 600, color: "var(--text-main)" }}>Area Units</span>
            <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>Preferred unit displayed for fields area</p>
          </div>

          <div className="unit-toggle">
            <button
              onClick={() => setAreaUnit("hectares")}
              className={`unit-btn ${areaUnit === "hectares" ? "active" : ""}`}
            >
              Hectares (ha)
            </button>
            <button
              onClick={() => setAreaUnit("acres")}
              className={`unit-btn ${areaUnit === "acres" ? "active" : ""}`}
            >
              Acres (ac)
            </button>
          </div>
        </div>
      </section>

      <section className="settings-section settings-section--security">
        <div className="settings-header">
          <div className="settings-badge settings-badge--red">
            <Shield size={22} />
          </div>
          <div>
            <h3 style={{ fontSize: "16px", fontWeight: 700 }}>Security Settings</h3>
            <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>Update your security credentials</p>
          </div>
        </div>

        {pwdError && (
          <div className="alert-container alert-danger">
            <AlertCircle size={18} style={{ flexShrink: 0 }} />
            <span>{pwdError}</span>
          </div>
        )}

        {pwdSuccess && (
          <div className="alert-container alert-success">
            <CheckCircle size={18} style={{ flexShrink: 0 }} />
            <span>{pwdSuccess}</span>
          </div>
        )}

        <form className="settings-password-form" onSubmit={handlePasswordChange} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div className="profile-grid">
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <label style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-main)" }}>Old Password</label>
              <input
                type="password"
                placeholder="••••••••"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <label style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-main)" }}>New Password</label>
              <input
                type="password"
                placeholder="••••••••"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>
          </div>

          <div className="profile-grid">
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <label style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-main)" }}>Confirm New Password</label>
              <input
                type="password"
                placeholder="••••••••"
                value={confirmNewPassword}
                onChange={(e) => setConfirmNewPassword(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>
          </div>

          <button
            type="submit"
            style={{
              padding: "12px 18px",
              backgroundColor: "var(--primary-green)",
              color: "white",
              borderRadius: "var(--border-radius-sm)",
              fontWeight: 600,
              alignSelf: "flex-start"
            }}
            disabled={isLoading}
          >
            {isLoading ? "Updating..." : "Update Password"}
          </button>
        </form>
      </section>

      <section className="settings-section settings-section--session">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "20px" }}>
          <div>
            <h3 style={{ fontSize: "16px", fontWeight: 700 }}>Session Logout</h3>
            <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>Sign out of your active browser session</p>
          </div>

          <button
            onClick={handleLogout}
            className="logout-action-btn"
          >
            <LogOut size={16} />
            <span>Logout Session</span>
          </button>
        </div>
      </section>
    </div>
  );
};

export default Settings;
