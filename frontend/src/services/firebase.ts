/**
 * Firebase Client SDK Initialization & Authentication Service.
 *
 * Configured via Vite environment variables:
 * - VITE_FIREBASE_API_KEY
 * - VITE_FIREBASE_AUTH_DOMAIN
 * - VITE_FIREBASE_PROJECT_ID
 * - VITE_FIREBASE_STORAGE_BUCKET
 * - VITE_FIREBASE_MESSAGING_SENDER_ID
 * - VITE_FIREBASE_APP_ID
 */
import { initializeApp, getApps, getApp, type FirebaseApp } from "firebase/app";
import {
  getAuth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  signOut as fbSignOut,
  onAuthStateChanged,
  onIdTokenChanged,
  updateProfile,
  type Auth,
  type User as FirebaseUser,
  type UserCredential,
} from "firebase/auth";

export interface FirebaseClientConfig {
  apiKey?: string;
  authDomain?: string;
  projectId?: string;
  storageBucket?: string;
  messagingSenderId?: string;
  appId?: string;
}

export const firebaseConfig: FirebaseClientConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

/**
 * Check if Firebase is properly configured with non-placeholder values.
 */
export function isFirebaseConfigured(): boolean {
  const { apiKey, projectId } = firebaseConfig;
  if (!apiKey || !projectId) return false;
  if (apiKey.includes("your-firebase") || projectId.includes("your-firebase")) return false;
  return apiKey.trim().length > 0 && projectId.trim().length > 0;
}

let appInstance: FirebaseApp | null = null;
let authInstance: Auth | null = null;

export function getFirebaseApp(): FirebaseApp {
  if (!isFirebaseConfigured()) {
    throw new Error(
      "Firebase is not configured. Please supply valid VITE_FIREBASE_* variables in .env"
    );
  }
  if (!appInstance) {
    if (getApps().length > 0) {
      appInstance = getApp();
    } else {
      appInstance = initializeApp(firebaseConfig as Record<string, string>);
    }
  }
  return appInstance;
}

export function getFirebaseAuth(): Auth {
  if (!authInstance) {
    const app = getFirebaseApp();
    authInstance = getAuth(app);
  }
  return authInstance;
}

/**
 * Retrieve the current user's valid Firebase ID token without storing it in localStorage/sessionStorage.
 * Firebase SDK manages token refresh and memory caching automatically.
 */
export async function getFirebaseIdToken(forceRefresh = false): Promise<string | null> {
  if (!isFirebaseConfigured()) return null;
  try {
    const auth = getFirebaseAuth();
    const user = auth.currentUser;
    if (!user) return null;
    return await user.getIdToken(forceRefresh);
  } catch {
    return null;
  }
}

/**
 * Format Firebase Auth errors into clear, actionable messages.
 */
export function formatFirebaseAuthError(error: any): string {
  const code = error?.code || "";
  switch (code) {
    case "auth/invalid-credential":
    case "auth/wrong-password":
    case "auth/user-not-found":
      return "Invalid email or password. Please verify your credentials.";
    case "auth/email-already-in-use":
      return "An account with this email already exists in Firebase. Please sign in.";
    case "auth/weak-password":
      return "Password should be at least 6 characters long.";
    case "auth/invalid-email":
      return "Please enter a valid email address.";
    case "auth/operation-not-allowed":
      return "This sign-in provider is not enabled in Firebase Console. Please enable Email/Password or Google provider.";
    case "auth/popup-closed-by-user":
      return "Sign-in popup was closed before completion.";
    case "auth/network-request-failed":
      return "Network error: Unable to reach Firebase Authentication servers.";
    case "auth/too-many-requests":
      return "Access temporarily blocked due to multiple failed login attempts. Please try again later.";
    default:
      return error?.message || "Authentication failed. Please check your credentials.";
  }
}

/**
 * Sign in with Email and Password using Firebase.
 */
export async function signInWithFirebaseEmail(
  email: string,
  password: string
): Promise<UserCredential> {
  const auth = getFirebaseAuth();
  return await signInWithEmailAndPassword(auth, email.trim(), password);
}

/**
 * Create a new account with Email and Password in Firebase.
 */
export async function signUpWithFirebaseEmail(
  email: string,
  password: string,
  fullName?: string
): Promise<UserCredential> {
  const auth = getFirebaseAuth();
  const credential = await createUserWithEmailAndPassword(auth, email.trim(), password);
  if (fullName && fullName.trim() && credential.user) {
    try {
      await updateProfile(credential.user, { displayName: fullName.trim() });
    } catch {
      // Non-critical profile update failure
    }
  }
  return credential;
}

/**
 * Sign in using Google OAuth Popup.
 */
export async function signInWithFirebaseGoogle(): Promise<UserCredential> {
  const auth = getFirebaseAuth();
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: "select_account" });
  return await signInWithPopup(auth, provider);
}

/**
 * Sign out from Firebase Authentication.
 */
export async function signOutFirebase(): Promise<void> {
  if (!isFirebaseConfigured()) return;
  try {
    const auth = getFirebaseAuth();
    await fbSignOut(auth);
  } catch {
    // Ignore sign-out failure
  }
}

/**
 * Subscribe to Firebase auth state changes.
 */
export function onFirebaseAuthStateChanged(
  callback: (user: FirebaseUser | null) => void
): () => void {
  if (!isFirebaseConfigured()) {
    callback(null);
    return () => {};
  }
  try {
    const auth = getFirebaseAuth();
    return onAuthStateChanged(auth, callback);
  } catch {
    callback(null);
    return () => {};
  }
}
