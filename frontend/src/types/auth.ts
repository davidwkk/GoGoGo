/**
 * Minimal user shape stored in the auth state.
 * Derived from the /auth/login and /auth/register responses.
 */
export interface AuthUser {
  email: string;
  username: string;
}

/**
 * Response shape returned by POST /auth/login and POST /auth/register.
 */
export interface AuthResponse {
  access_token: string;
  token_type: string;
}
