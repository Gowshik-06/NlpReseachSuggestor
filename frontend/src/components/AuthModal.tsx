import React, { useState, useEffect } from "react";
import type { User } from "../types/auth";
import { firebaseLogin, linkFirebaseAccount } from "../services/api";
import {
  signInWithFirebaseGoogle,
  formatFirebaseAuthError,
} from "../services/firebase";
import { KeyIcon } from "./icons/Icons";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthSuccess: (user: User) => void;
  initialMode?: "login" | "register" | "link";
}

export default function AuthModal({
  isOpen,
  onClose,
  onAuthSuccess,
  initialMode = "login",
}: AuthModalProps) {
  const [mode, setMode] = useState<"login" | "link">(
    initialMode === "link" ? "link" : "login"
  );
  const [linkPassword, setLinkPassword] = useState("");
  const [pendingFirebaseToken, setPendingFirebaseToken] = useState<string | null>(null);
  const [pendingEmail, setPendingEmail] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Synchronize state when modal is opened
  useEffect(() => {
    if (isOpen) {
      setMode(initialMode === "link" ? "link" : "login");
      setError(null);
      setPendingFirebaseToken(null);
      setPendingEmail("");
      setLinkPassword("");
    }
  }, [isOpen, initialMode]);

  // Support closing modal with Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !loading) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose, loading]);

  if (!isOpen) return null;

  const handleGoogleSignIn = async () => {
    setError(null);
    setLoading(true);
    try {
      const credential = await signInWithFirebaseGoogle();
      const idToken = await credential.user.getIdToken();
      const userEmail = credential.user.email || "";

      try {
        const res = await firebaseLogin(idToken);
        onAuthSuccess(res.user);
        onClose();
      } catch (loginErr: any) {
        const msg = loginErr?.message || "";
        if (msg.includes("409") || msg.toLowerCase().includes("already registered")) {
          // Account exists locally with this email; offer verified linking
          setPendingFirebaseToken(idToken);
          setPendingEmail(userEmail);
          setMode("link");
          setError(
            "An account with this email already exists in ResearchLens. " +
            "Please enter your existing password to verify ownership and link your Google identity."
          );
        } else {
          setError(loginErr.message || "Failed to sign in. Please try again.");
        }
      }
    } catch (err: any) {
      setError(formatFirebaseAuthError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleLinkSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pendingFirebaseToken) {
      setError("No active Google identity to link. Please try signing in again.");
      return;
    }
    if (!linkPassword) {
      setError("Please enter your existing local account password.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await linkFirebaseAccount({
        username_or_email: pendingEmail,
        local_password: linkPassword,
        firebase_token: pendingFirebaseToken,
      });
      onAuthSuccess(res.user);
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to link account. Please verify your password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="modal-backdrop"
      onClick={() => {
        if (!loading) onClose();
      }}
    >
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-label={mode === "link" ? "Link Account Dialog" : "Google Sign-In Dialog"}
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: "420px",
          padding: "2rem",
          position: "relative",
        }}
      >
        <button
          type="button"
          className="modal-close-btn"
          onClick={onClose}
          disabled={loading}
          style={{
            position: "absolute",
            top: "1rem",
            right: "1rem",
          }}
          aria-label="Close dialog"
        >
          ✕
        </button>

        <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "var(--radius-sm)",
              background: "var(--bg-subtle)",
              border: "1px solid var(--border-leaf)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 0.75rem",
              color: "var(--button-primary)",
            }}
          >
            <KeyIcon size={22} />
          </div>
          <h2 style={{ margin: "0 0 0.35rem", fontSize: "1.3rem", color: "var(--text-primary)", fontWeight: 700, fontFamily: "var(--font-serif)" }}>
            {mode === "link" ? "Link Existing Account" : "Researcher Access"}
          </h2>
          <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)", lineHeight: 1.45 }}>
            {mode === "link"
              ? "Verify control of your existing account to connect it with your Google identity"
              : "Sign in with your Google account to access your personal research library, evidence synthesis, and DRIUT impact alerts"}
          </p>
        </div>

        {error && (
          <div
            role="alert"
            style={{
              background: "#fef2f2",
              border: "1px solid #fecaca",
              borderRadius: "var(--radius-sm, 6px)",
              padding: "0.75rem 1rem",
              color: "#b91c1c",
              fontSize: "0.85rem",
              marginBottom: "1.25rem",
              display: "flex",
              alignItems: "flex-start",
              gap: "0.5rem",
              lineHeight: 1.4,
            }}
          >
            <span style={{ flexShrink: 0, marginTop: "1px" }}>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {mode === "link" ? (
          /* Link Existing Account Sub-Flow */
          <form onSubmit={handleLinkSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <p style={{ margin: 0, fontSize: "0.85rem", color: "#4b5563" }}>
              Existing account: <strong>{pendingEmail}</strong>
            </p>
            <div>
              <label
                htmlFor="link-password-input"
                style={{
                  display: "block",
                  fontSize: "0.82rem",
                  color: "#374151",
                  marginBottom: "0.35rem",
                  fontWeight: 600,
                }}
              >
                Local Account Password
              </label>
              <input
                id="link-password-input"
                type="password"
                className="search-input"
                value={linkPassword}
                onChange={(e) => setLinkPassword(e.target.value)}
                placeholder="Enter your existing account password"
                required
                autoFocus
                disabled={loading}
                style={{
                  width: "100%",
                  padding: "0.65rem 0.85rem",
                  fontSize: "0.92rem",
                  background: "#ffffff",
                  border: "1px solid #d1d5db",
                  color: "#1f2937",
                  borderRadius: "var(--radius-sm, 6px)",
                }}
              />
            </div>

            <button
              type="submit"
              className="search-btn"
              disabled={loading}
              style={{
                marginTop: "0.5rem",
                padding: "0.75rem",
                fontSize: "0.95rem",
                fontWeight: 600,
                cursor: loading ? "wait" : "pointer",
                opacity: loading ? 0.75 : 1,
                background: "#1f2937",
                color: "#ffffff",
                border: "1px solid #1f2937",
                borderRadius: "var(--radius-md, 8px)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "0.5rem",
              }}
            >
              {loading ? "Linking Account..." : "Confirm & Link Account →"}
            </button>

            <button
              type="button"
              disabled={loading}
              onClick={() => {
                setMode("login");
                setPendingFirebaseToken(null);
                setPendingEmail("");
                setError(null);
              }}
              style={{
                background: "transparent",
                border: "none",
                color: "#6b7280",
                fontSize: "0.82rem",
                cursor: loading ? "not-allowed" : "pointer",
                textAlign: "center",
                padding: "0.4rem",
              }}
            >
              ← Cancel and Return
            </button>
          </form>
        ) : (
          /* Single-Role Google Sign-In Flow */
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <button
              type="button"
              onClick={handleGoogleSignIn}
              disabled={loading}
              aria-label="Sign in with Google"
              style={{
                width: "100%",
                padding: "0.8rem 1.25rem",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "0.75rem",
                background: "#ffffff",
                border: "1px solid #d1d5db",
                borderRadius: "var(--radius-md, 8px)",
                color: "#1f2937",
                fontSize: "0.95rem",
                fontWeight: 600,
                cursor: loading ? "wait" : "pointer",
                boxShadow: "0 1px 3px rgba(0, 0, 0, 0.08)",
                transition: "all 0.15s ease-in-out",
                opacity: loading ? 0.7 : 1,
              }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
              <span>{loading ? "Signing in..." : "Continue with Google"}</span>
            </button>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "0.35rem",
                color: "var(--text-muted)",
                fontSize: "0.78rem",
                marginTop: "0.25rem",
              }}
            >
              <KeyIcon size={12} />
              <span>Single-role authentication protected by Firebase ID token verification</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
