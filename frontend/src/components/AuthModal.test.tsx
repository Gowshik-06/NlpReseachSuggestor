import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import AuthModal from "./AuthModal";
import * as firebaseService from "../services/firebase";
import * as apiService from "../services/api";

vi.mock("../services/firebase", () => ({
  signInWithFirebaseGoogle: vi.fn(),
  formatFirebaseAuthError: vi.fn((err: any) => err?.message || "Firebase error"),
}));

vi.mock("../services/api", () => ({
  firebaseLogin: vi.fn(),
  linkFirebaseAccount: vi.fn(),
}));

describe("AuthModal Component (Google Sign-In Only)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders with role dialog, aria-modal, and Google Sign-In button", () => {
    render(
      <AuthModal
        isOpen={true}
        onClose={vi.fn()}
        onAuthSuccess={vi.fn()}
        initialMode="login"
      />
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByText("Researcher Access")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in with google/i })).toBeInTheDocument();
  });

  it("closes when Escape key is pressed", () => {
    const onClose = vi.fn();
    render(
      <AuthModal
        isOpen={true}
        onClose={onClose}
        onAuthSuccess={vi.fn()}
        initialMode="login"
      />
    );

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("renders link account mode when initialMode is link", () => {
    render(
      <AuthModal
        isOpen={true}
        onClose={vi.fn()}
        onAuthSuccess={vi.fn()}
        initialMode="link"
      />
    );

    expect(screen.getByText("Link Existing Account")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/enter your existing account password/i)).toBeInTheDocument();
  });

  it("executes Google Sign-In flow and triggers onAuthSuccess", async () => {
    const onAuthSuccess = vi.fn();
    const onClose = vi.fn();
    const mockUser = { id: 42, username: "google_researcher", email: "res@gmail.com", is_active: true };

    (firebaseService.signInWithFirebaseGoogle as any).mockResolvedValue({
      user: {
        email: "res@gmail.com",
        getIdToken: vi.fn().mockResolvedValue("mock-google-id-token-xyz"),
      },
    });
    (apiService.firebaseLogin as any).mockResolvedValue({
      access_token: "mock-google-id-token-xyz",
      token_type: "bearer",
      user: mockUser,
    });

    render(
      <AuthModal
        isOpen={true}
        onClose={onClose}
        onAuthSuccess={onAuthSuccess}
      />
    );

    const googleBtn = screen.getByRole("button", { name: /sign in with google/i });
    fireEvent.click(googleBtn);

    await waitFor(() => {
      expect(firebaseService.signInWithFirebaseGoogle).toHaveBeenCalled();
      expect(apiService.firebaseLogin).toHaveBeenCalledWith("mock-google-id-token-xyz");
      expect(onAuthSuccess).toHaveBeenCalledWith(mockUser);
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("displays error alert when Google sign-in fails", async () => {
    (firebaseService.signInWithFirebaseGoogle as any).mockRejectedValue(
      new Error("Sign-in popup closed by user")
    );

    render(
      <AuthModal
        isOpen={true}
        onClose={vi.fn()}
        onAuthSuccess={vi.fn()}
      />
    );

    const googleBtn = screen.getByRole("button", { name: /sign in with google/i });
    fireEvent.click(googleBtn);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByText("Sign-in popup closed by user")).toBeInTheDocument();
    });
  });
});
