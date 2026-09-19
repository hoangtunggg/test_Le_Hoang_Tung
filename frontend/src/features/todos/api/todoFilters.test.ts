import { describe, expect, it } from "vitest";
import { normalizedTodoFilters, todoQueryKey } from "./todos";

describe("todo filter query keys", () => {
  const base = { status: "active" as const, tag_id: "tag-a", keyword: "  Quarterly ", date_from: "2026-01-01", date_to: "2026-01-31", page: 1, page_size: 20 };
  it("contains every normalized filter dimension", () => {
    expect(todoQueryKey(base)).toEqual(["todos", { ...base, keyword: "quarterly" }]);
  });
  it("changes for each filter and clears to stable defaults", () => {
    const variants = [base, { ...base, status: "completed" as const }, { ...base, tag_id: "tag-b" }, { ...base, keyword: "other" }, { ...base, date_from: "2026-02-01" }, { ...base, date_to: "2026-02-28" }, { ...base, page: 2 }, { ...base, page_size: 10 }];
    expect(new Set(variants.map((filters) => JSON.stringify(todoQueryKey(filters)))).size).toBe(variants.length);
    expect(normalizedTodoFilters()).toEqual({ status: "all", tag_id: "", keyword: "", date_from: "", date_to: "", page: 1, page_size: 20 });
  });
});
