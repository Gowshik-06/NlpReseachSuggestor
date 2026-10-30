import React from "react";
import type { HealthStatus } from "../types/health";
import type { User } from "../types/auth";
import {
  SearchIcon,
  DocumentIcon,
  EvolutionIcon,
  BookmarkIcon,
  ActivityIcon,
  CompareIcon,
  UserIcon,
  KeyIcon,
} from "./icons/Icons";

interface NavbarProps {
  activeTab: "explore" | "pdf" | "compare" | "saved" | "driut" | "evolution";
  setActiveTab: (tab: "explore" | "pdf" | "compare" | "saved" | "driut" | "evolution") => void;
  savedCount: number;
  driutUnreadCount: number;
  compareCount: number;
  onOpenCompare: () => void;
  health: HealthStatus | null;
  currentUser?: User | null;
  onOpenAuth?: (mode?: "login" | "register") => void;
  onLogout?: () => void;
}

export default function Navbar({
  activeTab,
  setActiveTab,
  savedCount,
  driutUnreadCount,
  compareCount,
  onOpenCompare,
  health,
  currentUser = null,
  onOpenAuth,
  onLogout,
}: NavbarProps) {
  const isHealthy = health?.status === "ok" || health?.status === "degraded";
  const dbConnected = health?.database === "connected";

  return (
    <header className="header-bar">
      <div className="brand-section">
        <div className="brand-logo-badge" title="ResearchLens Observatory">
          RL
        </div>
        <div className="brand-text">
          <h1>ResearchLens</h1>
          <div className="brand-sub">Semantic Research Discovery &amp; Intelligence</div>
        </div>
      </div>

      <nav className="nav-tabs" aria-label="Main Navigation">
        <button
          type="button"
          className={`nav-tab-btn ${activeTab === "explore" ? "active" : ""}`}
          onClick={() => setActiveTab("explore")}
        >
          <SearchIcon size={15} />
          <span>Explore</span>
        </button>

        <button
          type="button"
          className={`nav-tab-btn ${activeTab === "pdf" ? "active" : ""}`}
          onClick={() => setActiveTab("pdf")}
        >
          <DocumentIcon size={15} />
          <span>PDF Manuscript</span>
        </button>

        <button
          type="button"
          className={`nav-tab-btn ${activeTab === "evolution" ? "active" : ""}`}
          onClick={() => setActiveTab("evolution")}
        >
          <EvolutionIcon size={15} />
          <span>Evolution &amp; Gaps</span>
        </button>

        <button
          type="button"
          className={`nav-tab-btn ${activeTab === "saved" ? "active" : ""}`}
          onClick={() => setActiveTab("saved")}
        >
          <BookmarkIcon size={15} />
          <span>Saved Library</span>
          {savedCount > 0 && <span className="tab-badge">{savedCount}</span>}
        </button>

        <button
          type="button"
          className={`nav-tab-btn ${activeTab === "driut" ? "active" : ""}`}
          onClick={() => setActiveTab("driut")}
        >
          <ActivityIcon size={15} />
          <span>DRIUT Alerts</span>
          {driutUnreadCount > 0 && (
            <span className="tab-badge pulse">{driutUnreadCount}</span>
          )}
        </button>
      </nav>

      <div className="header-actions">
        {compareCount > 0 && (
          <button
            type="button"
            onClick={onOpenCompare}
            className="btn-secondary header-btn"
            title="Open side-by-side paper comparison"
          >
            <CompareIcon size={14} />
            <span>Compare ({compareCount})</span>
          </button>
        )}

        {currentUser ? (
          <div className="user-identity-badge">
            <UserIcon size={14} />
            <span className="user-name">{currentUser.username}</span>
            {onLogout && (
              <button
                type="button"
                onClick={onLogout}
                className="user-logout-btn"
                title="Sign out"
              >
                (Sign Out)
              </button>
            )}
          </div>
        ) : (
          onOpenAuth && (
            <button
              type="button"
              onClick={() => onOpenAuth("login")}
              className="btn-secondary header-btn"
            >
              <KeyIcon size={14} />
              <span>Sign In</span>
            </button>
          )
        )}

        <div className="system-status-indicator">
          <span
            className="status-dot"
            style={{
              background: isHealthy && dbConnected ? "var(--emerald)" : "var(--amber)",
            }}
          />
          <span>{dbConnected ? "System Online" : "Degraded (No DB)"}</span>
        </div>
      </div>
    </header>
  );
}
