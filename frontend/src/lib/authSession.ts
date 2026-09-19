import { queryClient } from "./queryClient.js";

export const USER_SCOPED_QUERY_KEYS = [["currentUser"], ["todos"], ["tags"]] as const;

interface AuthTokens {
  access_token: string;
  refresh_token: string;
}

export function clearUserScopedQueryCache(): void {
  for (const queryKey of USER_SCOPED_QUERY_KEYS) {
    queryClient.removeQueries({ queryKey });
  }
}

export function establishAuthSession(tokens: AuthTokens): void {
  clearUserScopedQueryCache();
  localStorage.setItem("access_token", tokens.access_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);
}

export function clearAuthSession(): void {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  clearUserScopedQueryCache();
}
