import { render, screen, fireEvent } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it, vi, afterEach } from "vitest";
import App from "./App";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function renderApp() {
  return render(
    <BrowserRouter>
      <App />
    </BrowserRouter>
  );
}

describe("App", () => {
  it("renders the ResearchLens recommendation application shell", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderApp();
    expect(screen.getByText("ResearchLens")).toBeInTheDocument();
    expect(screen.getByText("Semantic Research Discovery & Intelligence")).toBeInTheDocument();
  });

  it("renders navigation tabs for Explore, PDF Manuscript, Saved Library, and DRIUT Alerts", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderApp();
    expect(screen.getByRole("button", { name: /Explore/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /PDF Manuscript/i })).toBeInTheDocument();
    expect(screen.getByText(/Saved Library/)).toBeInTheDocument();
    expect(screen.getByText(/DRIUT Alerts/)).toBeInTheDocument();
  });

  it("renders Sign In button when unauthenticated and opens Researcher Access modal on click", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderApp();

    const signInBtn = screen.getByRole("button", { name: /Sign In/i });
    expect(signInBtn).toBeInTheDocument();

    fireEvent.click(signInBtn);
    expect(screen.getByText("Researcher Access")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in with google/i })).toBeInTheDocument();
  });

  it("displays private sanctuary isolation prompt when accessing Saved Library while unauthenticated", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderApp();

    const savedTab = screen.getByText(/Saved Library/);
    fireEvent.click(savedTab);

    expect(screen.getByText("Private Literature Sanctuary")).toBeInTheDocument();
    expect(
      screen.getByText(/Your bookmarked papers, custom tags, and private notes are cryptographically isolated/)
    ).toBeInTheDocument();
  });

  it("opens main dashboard directly on /dashboard route without sign-in redirect", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    window.history.pushState({}, "Dashboard", "/dashboard");
    renderApp();
    expect(screen.getByText("ResearchLens")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Explore/i })).toBeInTheDocument();
  });

  it("redirects /login and /register directly to main dashboard without auth modal", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    window.history.pushState({}, "Login", "/login");
    renderApp();
    expect(screen.getByText("ResearchLens")).toBeInTheDocument();
    expect(screen.queryByText("Researcher Access")).not.toBeInTheDocument();
  });

  it("initializes search sort order to Relevance by default and allows switching to Recency", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderApp();

    const relBtn = screen.getByRole("button", { name: /Relevance/i });
    expect(relBtn).toHaveClass("active");

    const recBtn = screen.getByRole("button", { name: /2026 Latest First/i });
    expect(recBtn).not.toHaveClass("active");

    fireEvent.click(recBtn);
    expect(recBtn).toHaveClass("active");
    expect(relBtn).not.toHaveClass("active");

    // Switch back to Relevance
    fireEvent.click(relBtn);
    expect(relBtn).toHaveClass("active");
    expect(recBtn).not.toHaveClass("active");
  });
});

