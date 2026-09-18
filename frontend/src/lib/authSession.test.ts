import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
import {
  clearAuthSession,
  establishAuthSession,
} from "./authSession";
import { queryClient } from "./queryClient";

function createMemoryStorage(): Storage {
  const values = new Map<string, string>();

  return {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => Array.from(values.keys())[index] ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, value),
  };
}

function seedUserAData(): void {
  queryClient.setQueryData(["currentUser"], {
    id: "user-a",
    email: "user-a@example.com",
  });
  queryClient.setQueryData(["todos"], [{ id: "todo-a", title: "Private" }]);
}

describe("authentication session cache boundaries", () => {
  beforeEach(() => {
    queryClient.clear();
    vi.stubGlobal("localStorage", createMemoryStorage());
    vi.stubGlobal("window", { location: { href: "/" } });
  });

  afterEach(() => {
    queryClient.clear();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("clears private cache data when the session ends", () => {
    seedUserAData();
    queryClient.setQueryData(["publicReference"], { retained: true });
    localStorage.setItem("access_token", "user-a-access");
    localStorage.setItem("refresh_token", "user-a-refresh");

    clearAuthSession();

    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
    expect(queryClient.getQueryData(["currentUser"])).toBeUndefined();
    expect(queryClient.getQueryData(["todos"])).toBeUndefined();
    expect(queryClient.getQueryData(["publicReference"])).toEqual({
      retained: true,
    });
  });

  it("removes the previous identity cache before establishing a new session", () => {
    seedUserAData();
    localStorage.setItem("access_token", "user-a-access");
    localStorage.setItem("refresh_token", "user-a-refresh");

    establishAuthSession({
      access_token: "user-b-access",
      refresh_token: "user-b-refresh",
    });

    expect(queryClient.getQueryData(["currentUser"])).toBeUndefined();
    expect(queryClient.getQueryData(["todos"])).toBeUndefined();
    expect(localStorage.getItem("access_token")).toBe("user-b-access");
    expect(localStorage.getItem("refresh_token")).toBe("user-b-refresh");
  });

  it("clears private cache data when an API response returns 401", async () => {
    seedUserAData();
    localStorage.setItem("access_token", "expired-access");
    localStorage.setItem("refresh_token", "user-a-refresh");

    const unauthorized = { response: { status: 401 } };

    await expect(
      api.get("/protected", {
        adapter: async () => Promise.reject(unauthorized),
      })
    ).rejects.toBe(unauthorized);

    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
    expect(queryClient.getQueryData(["currentUser"])).toBeUndefined();
    expect(queryClient.getQueryData(["todos"])).toBeUndefined();
    expect(window.location.href).toBe("/login");
  });
});
