import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryClient } from "@/lib/queryClient";
import type { Tag } from "@/features/todos/api/todos";
export const tagsQueryKey = ["tags"] as const;
export function useTags() { return useQuery({ queryKey: tagsQueryKey, queryFn: async () => (await api.get("/tags")).data as Tag[] }); }
const invalidateTagsAndTodos = () => Promise.all([queryClient.invalidateQueries({ queryKey: tagsQueryKey }), queryClient.invalidateQueries({ queryKey: ["todos"] })]);
export function useCreateTag() { return useMutation({ mutationFn: async (data: { name: string; color?: string }) => (await api.post("/tags", data)).data as Tag, onSuccess: invalidateTagsAndTodos }); }
export function useUpdateTag() { return useMutation({ mutationFn: async ({ id, ...data }: { id: string; name?: string; color?: string | null }) => (await api.patch(`/tags/${id}`, data)).data as Tag, onSuccess: invalidateTagsAndTodos }); }
export function useDeleteTag() { return useMutation({ mutationFn: async (id: string) => { await api.delete(`/tags/${id}`); }, onSuccess: invalidateTagsAndTodos }); }
