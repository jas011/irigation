import React, { useState, useEffect, createContext, useContext } from "react";
import { Link, useLocation, useNavigate, Outlet } from "react-router-dom";
import {
  LayoutDashboard,
  History,
  CloudSun,
  Settings,
  LogOut,
  Calendar,
  Bell,
  User,
  Menu,
  ChevronLeft,
  ChevronRight
} from "lucide-react";
import ApiService from "../services/api";
import sideBG from "../assets/sideBG.png";
import "../App.css"
// Create context to share active Field ID across Dashboard / History
interface FieldContextType {
  activeFieldId: string | null;
  setActiveFieldId: React.Dispatch<React.SetStateAction<string | null>>;
  selectedFieldData: any | null;
  setSelectedFieldData: React.Dispatch<React.SetStateAction<any | null>>;
  areaUnit: "hectares" | "acres";
  setAreaUnit: (unit: "hectares" | "acres") => void;
  mapOverlayMode: "none" | "crop" | "moisture";
  setMapOverlayMode: (mode: "none" | "crop" | "moisture") => void;
  cropGrid: any | null;
  setCropGrid: (grid: any | null) => void;
  moistureGrid: any | null;
  setMoistureGrid: (grid: any | null) => void;
}

export const FieldContext = createContext<FieldContextType>({
  activeFieldId: null,
  setActiveFieldId: () => { },
  selectedFieldData: null,
  setSelectedFieldData: () => { },
  areaUnit: "hectares",
  setAreaUnit: () => { },
  mapOverlayMode: "none",
  setMapOverlayMode: () => { },
  cropGrid: null,
  setCropGrid: () => { },
  moistureGrid: null,
  setMoistureGrid: () => { },
});

export const useFieldContext = () => useContext(FieldContext);

const DashboardLayout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [user, setUser] = useState<{ name: string; email: string } | null>(null);

  // Layout States
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Shared field info
  const [activeFieldId, setActiveFieldId] = useState<string | null>(null);
  const [selectedFieldData, setSelectedFieldData] = useState<any | null>(null);
  const [areaUnit, setAreaUnit] = useState<"hectares" | "acres">("hectares");

  // Shared map overlay info
  const [mapOverlayMode, setMapOverlayMode] = useState<"none" | "crop" | "moisture">("none");
  const [cropGrid, setCropGrid] = useState<any | null>(null);
  const [moistureGrid, setMoistureGrid] = useState<any | null>(null);

  // Dynamic Season from OpenAI
  const [currentSeason, setCurrentSeason] = useState<string>("Kharif Season 2026");

  useEffect(() => {
    ApiService.getCurrentSeason()
      .then((data) => {
        if (data?.season_name) {
          setCurrentSeason(data.season_name);
        }
      })
      .catch((err) => {
        console.warn("Could not fetch current season from AI:", err);
      });
  }, []);

  useEffect(() => {
    if (!ApiService.isAuthenticated()) {
      navigate("/login");
      return;
    }


    ApiService.getMe()
      .then((data) => setUser(data))
      .catch(() => {
        ApiService.logout();
        navigate("/login");
      });
  }, [navigate]);

  useEffect(() => {
    if (selectedFieldData) {
      localStorage.setItem("agrisense_selected_field", JSON.stringify(selectedFieldData));
      localStorage.setItem("agrisense_active_field_id", activeFieldId || "");
    } else {
      localStorage.removeItem("agrisense_selected_field");
      localStorage.removeItem("agrisense_active_field_id");
    }
  }, [activeFieldId, selectedFieldData]);

  useEffect(() => {
    const savedField = localStorage.getItem("agrisense_selected_field");
    const savedFieldId = localStorage.getItem("agrisense_active_field_id");
    if (savedField && savedFieldId) {
      try {
        setSelectedFieldData(JSON.parse(savedField));
        setActiveFieldId(savedFieldId);
      } catch {
        localStorage.removeItem("agrisense_selected_field");
        localStorage.removeItem("agrisense_active_field_id");
      }
    }
  }, []);

  const handleLogout = () => {
    ApiService.logout();
    localStorage.removeItem("agrisense_selected_field");
    localStorage.removeItem("agrisense_active_field_id");
    navigate("/login");
  };

  const navItems = [
    { path: "/area-selection", label: "Area Selection", icon: LayoutDashboard },
    { path: "/history", label: "History", icon: History },
    { path: "/weather", label: "Weather", icon: CloudSun },
    { path: "/settings", label: "Settings", icon: Settings },
  ];

  const currentDateStr = new Date().toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric"
  });

  return (
    <FieldContext.Provider
      value={{
        activeFieldId,
        setActiveFieldId,
        selectedFieldData,
        setSelectedFieldData,
        areaUnit,
        setAreaUnit,
        mapOverlayMode,
        setMapOverlayMode,
        cropGrid,
        setCropGrid,
        moistureGrid,
        setMoistureGrid
      }}
    >
      <div className="layout-container" style={{ display: "flex", height: "100vh", overflow: "hidden" }}>

        {/* Sidebar backdrop for mobile */}
        {isMobileMenuOpen && (
          <div
            onClick={() => setIsMobileMenuOpen(false)}
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              backgroundColor: "rgba(0,0,0,0.5)",
              zIndex: 99,
            }}
          />
        )}

        {/* LEFT SIDEBAR */}
        <aside
          style={{
            width: isSidebarCollapsed ? "var(--sidebar-collapsed-width)" : "var(--sidebar-width)",
            backgroundImage: `url(${sideBG})`,
            backgroundSize: "cover",
            backgroundPosition: "center",
            backgroundRepeat: "no-repeat",
            color: "var(--sidebar-text)",
            borderRight: "1px solid var(--sidebar-border)",
            display: "flex",
            flexDirection: "column",
            transition: "width 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
            zIndex: 100,
            position: "relative",
          }}
          className={`sidebar-shell ${isMobileMenuOpen ? "mobile-open" : ""}`}
        >
          {/* Logo and Brand */}
          <div
            style={{
              padding: "24px 16px",
              display: "flex",
              alignItems: "center",
              gap: "12px",
              borderBottom: "1px solid var(--sidebar-border)",
              overflow: "hidden",
              whiteSpace: "nowrap"
            }}
          >
            {/* AgriSense Logo (Leaf Icon) */}
            <div
              style={{
                width: "40px",
                height: "40px",
                borderRadius: "8px",
                backgroundColor: "#166534",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2C12 2 6 7 6 12C6 16.4 9.6 20 14 20C17.4 20 18 17 18 15C18 10 12 2 12 2Z" fill="#22c55e" />
                <path d="M12 2C12 2 16 6 16 10C16 13 14 15 12 15C10 15 9 13.5 9 12C9 9 12 2 12 2Z" fill="#4ade80" />
                <path d="M12 15V22" stroke="#166534" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </div>

            {!isSidebarCollapsed && (
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span style={{ fontSize: "24px", fontWeight: "bold", color: "#ffffff", fontFamily: "var(--font-primary)" }}>AgriSense</span>
                <span style={{ fontSize: "16px", color: "#22c55e", fontWeight: 500 }}>AI Irrigation Advisor</span>
              </div>
            )}
          </div>

          {/* Navigation Links */}
          <nav style={{ flex: 1, padding: "20px 12px", display: "flex", flexDirection: "column", gap: "6px" }}>
            {navItems.map((item) => {
              const isActive = location.pathname === item.path;
              const Icon = item.icon;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={(event) => {
                    event.preventDefault();
                    setIsMobileMenuOpen(false);
                    navigate(item.path);
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "12px",
                    padding: "12px 14px",
                    borderRadius: "8px",
                    textDecoration: "none",
                    color: isActive ? "var(--sidebar-text-active)" : "var(--sidebar-text)",
                    backgroundColor: isActive ? "var(--sidebar-active-bg)" : "transparent",
                    transition: "all 0.2s",
                    fontWeight: isActive ? 600 : 500,
                  }}
                  className="nav-link-item"
                >
                  <Icon size={20} color={isActive ? "#22c55e" : "var(--sidebar-text)"} />
                  {!isSidebarCollapsed && <span>{item.label}</span>}
                </Link>
              );
            })}
          </nav>

          {/* Bottom Sidebar Collapse & Logout */}
          <div
            style={{
              padding: "16px 12px",
              borderTop: "1px solid var(--sidebar-border)",
              display: "flex",
              flexDirection: "column",
              gap: "8px"
            }}
          >
            <button
              onClick={handleLogout}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                padding: "12px 14px",
                width: "100%",
                borderRadius: "8px",
                color: "#ef4444",
                textAlign: "left",
              }}
              className="nav-link-item logout-btn"
            >
              <LogOut size={20} />
              {!isSidebarCollapsed && <span>Logout</span>}
            </button>

            <button
              onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: isSidebarCollapsed ? "center" : "flex-end",
                padding: "8px",
                width: "100%",
                borderRadius: "8px",
                color: "var(--sidebar-text)",
                marginTop: "4px"
              }}
              className="collapse-btn-desktop"
            >
              {isSidebarCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
            </button>
          </div>
        </aside>

        {/* MAIN BODY AREA */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

          {/* TOP HEADER */}
          <header className="app-topbar">
            {/* Mobile Sidebar Toggle & Page Title */}
            <div className="topbar-title-group">
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="mobile-menu-toggle topbar-icon-button"
              >
                <Menu size={24} />
              </button>
              <div>
                <span className="topbar-eyebrow">AgriSense workspace</span>
                <h2 className="topbar-page-title">
                  {location.pathname === "/area-selection" && "Field intelligence"}
                  {location.pathname === "/crop-analysis" && "Crop analysis"}
                  {location.pathname === "/moisture-analysis" && "Soil moisture analysis"}
                  {location.pathname === "/history" && "Field library"}
                  {location.pathname === "/weather" && "Weather intelligence"}
                  {location.pathname === "/settings" && "Account settings"}
                </h2>
              </div>
            </div>

            {/* Header Widgets / Status area */}
            <div className="header-meta-group">
              {/* Active Field Badge & Season Info */}
              <div className="header-field-badge">
                <span className="field-badge-season"><i />{currentSeason}</span>
                <span className="field-badge-id">
                  {activeFieldId ? `Field ID: ${activeFieldId}` : "No Field Selected"}
                </span>
              </div>

              {/* Date */}
              <div className="topbar-date">
                <Calendar size={14} />
                <span>{currentDateStr}</span>
              </div>

              {/* Notification Bell */}
              <button className="topbar-icon-button notification-button" aria-label="View notifications">
                <Bell size={20} />
                <span className="notification-dot" />
              </button>

              {/* User Avatar */}
              <button
                className="topbar-profile"
                onClick={() => navigate("/settings")}
                aria-label="Open account settings"
              >
                <span className="topbar-avatar">
                  {user ? user.name.charAt(0).toUpperCase() : <User size={18} />}
                </span>
                {!isSidebarCollapsed && user && (
                  <span className="header-username">
                    <span>{user.name}</span>
                    <small>Farm manager</small>
                  </span>
                )}
              </button>

            </div>
          </header>

          {/* MAIN PAGE VIEW CONTENT */}
          <main style={{ flex: 1, overflowY: "auto", padding: "2px"  }} className="main-content-scroll">
            <Outlet />
          </main>

        </div>
      </div>

      {/* Styled Responsive overrides using standard CSS inject */}
      <style>{`
        @media (max-width: 1024px) {
          .weather-badges-container {
            display: none !important;
          }
        }
        @media (max-width: 768px) {
          .mobile-menu-toggle {
            display: block !important;
          }
          .sidebar-shell {
            position: fixed !important;
            top: 0;
            left: 0;
            height: 100vh;
            width: var(--sidebar-width) !important;
            transform: translateX(-100%);
            transition: transform 0.3s ease;
          }
          .sidebar-shell.mobile-open {
            transform: translateX(0);
          }
          .collapse-btn-desktop {
            display: none !important;
          }
          .header-meta-group {
            gap: 12px !important;
          }
          .header-field-badge, .header-username {
            display: none !important;
          }
        }
      `}</style>
    </FieldContext.Provider>
  );
};

export default DashboardLayout;
