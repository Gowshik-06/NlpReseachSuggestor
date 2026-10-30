import { describe, expect, it, vi, beforeEach } from "vitest";
import {
  isFirebaseConfigured,
  formatFirebaseAuthError,
  getFirebaseIdToken,
  signOutFirebase,
  onFirebaseAuthStateChanged,
  firebaseConfig,
} from "./firebase";
import * as firebaseAuth from "firebase/auth";

vi.mock("firebase/app", () => ({
  initializeApp: vi.fn(() => ({})),
  getApps: vi.fn(() => [{}]),
  getApp: vi.fn(() => ({})),
}));

vi.mock("firebase/auth", () => ({
  getAuth: vi.fn(() => ({
    currentUser: {
      getIdToken: vi.fn().mockResolvedValue("mock-firebase-id-token-xyz"),
    },
  })),
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signInWithPopup: vi.fn(),
  GoogleAuthProvider: vi.fn(() => ({
    setCustomParameters: vi.fn(),
  })),
  signOut: vi.fn().mockResolvedValue(undefined),
  onAuthStateChanged: vi.fn((auth, cb) => {
    cb({ uid: "mock-uid-123", email: "test@firebase.local" });
    return vi.fn();
  }),
  onIdTokenChanged: vi.fn(),
  updateProfile: vi.fn().mockResolvedValue(undefined),
}));

describe("Firebase Service Module", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Configuration Detection", () => {
    it("recognizes placeholder or empty configurations as unconfigured", () => {
      const origApiKey = firebaseConfig.apiKey;
      firebaseConfig.apiKey = "your-firebase-web-api-key";
      expect(isFirebaseConfigured()).toBe(false);
      firebaseConfig.apiKey = origApiKey;
    });

    it("recognizes valid configuration values", () => {
      const origKey = firebaseConfig.apiKey;
      const origProj = firebaseConfig.projectId;
      firebaseConfig.apiKey = "AIzaSyValidProductionApiKey123";
      firebaseConfig.projectId = "researchlens-prod-project";
      expect(isFirebaseConfigured()).toBe(true);
      firebaseConfig.apiKey = origKey;
      firebaseConfig.projectId = origProj;
    });
  });

  describe("Error Formatting", () => {
    it("formats known Firebase Auth error codes into clear messages", () => {
      expect(formatFirebaseAuthError({ code: "auth/invalid-credential" })).toContain("Invalid email or password");
      expect(formatFirebaseAuthError({ code: "auth/operation-not-allowed" })).toContain("not enabled in Firebase Console");
      expect(formatFirebaseAuthError({ code: "auth/email-already-in-use" })).toContain("already exists");
      expect(formatFirebaseAuthError({ code: "auth/network-request-failed" })).toContain("Unable to reach Firebase");
      expect(formatFirebaseAuthError({ code: "auth/popup-closed-by-user" })).toContain("popup was closed");
      expect(formatFirebaseAuthError({ message: "Custom failure" })).toBe("Custom failure");
    });
  });

  describe("Token Retrieval and Auth State", () => {
    it("retrieves ID token from active currentUser without localStorage reliance", async () => {
      const origKey = firebaseConfig.apiKey;
      const origProj = firebaseConfig.projectId;
      firebaseConfig.apiKey = "valid_key";
      firebaseConfig.projectId = "valid_proj";

      const token = await getFirebaseIdToken();
      expect(token).toBe("mock-firebase-id-token-xyz");

      firebaseConfig.apiKey = origKey;
      firebaseConfig.projectId = origProj;
    });

    it("triggers callbacks on auth state changes", () => {
      const origKey = firebaseConfig.apiKey;
      const origProj = firebaseConfig.projectId;
      firebaseConfig.apiKey = "valid_key";
      firebaseConfig.projectId = "valid_proj";

      const callback = vi.fn();
      const unsubscribe = onFirebaseAuthStateChanged(callback);
      expect(callback).toHaveBeenCalledWith(expect.objectContaining({ uid: "mock-uid-123" }));
      expect(typeof unsubscribe).toBe("function");

      firebaseConfig.apiKey = origKey;
      firebaseConfig.projectId = origProj;
    });

    it("calls signOut on auth instance when logging out", async () => {
      const origKey = firebaseConfig.apiKey;
      const origProj = firebaseConfig.projectId;
      firebaseConfig.apiKey = "valid_key";
      firebaseConfig.projectId = "valid_proj";

      await signOutFirebase();
      expect(firebaseAuth.signOut).toHaveBeenCalled();

      firebaseConfig.apiKey = origKey;
      firebaseConfig.projectId = origProj;
    });
  });
});
