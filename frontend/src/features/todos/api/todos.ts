import { useMutation, useQuery } from "@tanstack/react-query";
import type { QueryClient, UseMutationOptions } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { queryClient } from "@/lib/queryClient";

export interface Tag { id: string; user_id: string; name: string; color: string | null; created_at: string; updated_at: string }
export interface Todo { id: string; title: string; description: string | null; completed: boolean; user_id: string; created_at: string; updated_at: string; tags?: Tag[] }
export interface TodoListResponse { items: Todo[]; total: number; page: number; size: number }
export interface TodoFilters { status?: "active" | "completed" | "all"; tag_id?: string; keyword?: string; date_from?: string; date_to?: string; page?: number; page_size?: number }
interface CreateTodoRequest { title: string; description?: string }
interface UpdateTodoRequest { title?: string; description?: string; completed?: boolean }
interface UpdateTodoVariables { id: string; data: UpdateTodoRequest }
interface UpdateTodoContext { previousTodos: Array<[readonly unknown[], TodoListResponse | undefined]> }

export function normalizedTodoFilters(filters: TodoFilters = {}): Required<TodoFilters> { return { status: filters.status ?? "all", tag_id: filters.tag_id ?? "", keyword: filters.keyword?.trim().toLocaleLowerCase() ?? "", date_from: filters.date_from ?? "", date_to: filters.date_to ?? "", page: filters.page ?? 1, page_size: filters.page_size ?? 20 }; }
export function todoQueryKey(filters: TodoFilters = {}) { return ["todos", normalizedTodoFilters(filters)] as const; }
export function useTodos(filters: TodoFilters = {}) { const normalized = normalizedTodoFilters(filters); return useQuery({ queryKey: todoQueryKey(normalized), queryFn: async (): Promise<TodoListResponse> => (await api.get("/todos", { params: normalized })).data }); }
const invalidateTodos = () => queryClient.invalidateQueries({ queryKey: ["todos"] });
export function useCreateTodo() { return useMutation({ mutationFn: async (data: CreateTodoRequest) => (await api.post("/todos", data)).data as Todo, onSuccess: () => { invalidateTodos(); toast.success("Todo created successfully!"); }, onError: () => toast.error("Failed to create todo") }); }
export function createUpdateTodoMutationOptions(client: QueryClient = queryClient): UseMutationOptions<Todo, unknown, UpdateTodoVariables, UpdateTodoContext> { return { mutationFn: async ({ id, data }) => (await api.put(`/todos/${id}`, data)).data, onMutate: async ({ id, data }) => { await client.cancelQueries({ queryKey: ["todos"] }); const previousTodos = client.getQueriesData<TodoListResponse>({ queryKey: ["todos"] }); client.setQueriesData<TodoListResponse>({ queryKey: ["todos"] }, (old) => old ? { ...old, items: old.items.map((todo) => todo.id === id ? { ...todo, ...data } : todo) } : old); return { previousTodos }; }, onError: (_error, _variables, context) => { context?.previousTodos.forEach(([key, value]) => client.setQueryData(key, value)); toast.error("Failed to update todo"); }, onSettled: () => client.invalidateQueries({ queryKey: ["todos"] }) }; }
export function useUpdateTodo() { return useMutation(createUpdateTodoMutationOptions()); }
export function useDeleteTodo() { return useMutation({ mutationFn: async (id: string) => { await api.delete(`/todos/${id}`); }, onSuccess: () => { invalidateTodos(); toast.success("Todo deleted successfully!"); }, onError: () => toast.error("Failed to delete todo") }); }
export function useToggleTodo() { const updateTodo = useUpdateTodo(); return { ...updateTodo, mutate: (todo: Todo) => updateTodo.mutate({ id: todo.id, data: { completed: !todo.completed } }) }; }
export function useBulkStatus() { return useMutation({ mutationFn: async ({ todo_ids, completed }: { todo_ids: string[]; completed: boolean }) => (await api.patch("/todos/bulk-status", { todo_ids, completed })).data as Todo[], onSuccess: () => { invalidateTodos(); toast.success("Todos updated successfully!"); }, onError: () => toast.error("Failed to update todos") }); }
export function useAttachTag() { return useMutation({ mutationFn: async ({ todoId, tagId }: { todoId: string; tagId: string }) => { await api.post(`/todos/${todoId}/tags`, { tag_id: tagId }); }, onSuccess: invalidateTodos, onError: () => toast.error("Failed to attach tag") }); }
