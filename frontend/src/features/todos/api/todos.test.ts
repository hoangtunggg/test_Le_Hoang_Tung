import { MutationObserver, QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import {
  createUpdateTodoMutationOptions,
  type Todo,
} from "./todos";

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

describe("optimistic todo updates", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("restores the previous snapshot after a failed mutation", async () => {
    const client = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    const todo: Todo = {
      id: "todo-1",
      title: "Original title",
      description: "Original description",
      completed: false,
      user_id: "user-a",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    const previousTodos = {
      items: [todo],
      total: 1,
      page: 1,
      size: 10000,
    };
    client.setQueryData(["todos"], previousTodos);

    let rejectRequest: (error: Error) => void = () => undefined;
    const pendingRequest = new Promise<never>((_resolve, reject) => {
      rejectRequest = reject;
    });
    vi.spyOn(api, "put").mockReturnValue(pendingRequest);
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");
    const observer = new MutationObserver(
      client,
      createUpdateTodoMutationOptions(client)
    );

    const mutation = observer.mutate({
      id: todo.id,
      data: { title: "Optimistic title", completed: true },
    });
    const rejectedMutation = expect(mutation).rejects.toThrow("server rejected");

    await vi.waitFor(() => {
      expect(client.getQueryData<typeof previousTodos>(["todos"])).toEqual({
        ...previousTodos,
        items: [
          {
            ...todo,
            title: "Optimistic title",
            completed: true,
          },
        ],
      });
    });

    rejectRequest(new Error("server rejected"));
    await rejectedMutation;

    expect(client.getQueryData(["todos"])).toEqual(previousTodos);
    expect(toast.error).toHaveBeenCalledWith("Failed to update todo");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["todos"] });

    client.clear();
  });
});
