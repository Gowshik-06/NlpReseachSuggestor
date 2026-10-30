/**
 * TypeScript types for User authentication and sessions.
 */
export interface User {
  id: number;
  username: string;
  email: string;
  full_name?: string | null;
  is_active: boolean;
  is_superuser?: boolean;
  firebase_uid?: string | null;
  created_at?: string | null;
}

export interface UserLoginRequest {
  username: string;
  password: string;
}

export interface UserRegisterRequest {
  username: string;
  email: string;
  password: string;
  full_name?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface FirebaseLoginRequest {
  id_token: string;
}

export interface LinkFirebaseAccountRequest {
  firebase_token: string;
  local_password: string;
  username_or_email?: string;
}

export interface LinkFirebaseAccountResponse {
  status: string;
  message: string;
  user: User;
}
