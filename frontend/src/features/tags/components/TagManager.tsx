import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCreateTag, useDeleteTag, useTags, useUpdateTag } from "../api/tags";
import { tagSchema, type TagFormData } from "../schemas/tag";

export function TagManager() {
  const { data: tags = [] } = useTags();
  const createTag = useCreateTag(); const updateTag = useUpdateTag(); const deleteTag = useDeleteTag();
  const { register, handleSubmit, reset, formState: { errors } } = useForm<TagFormData>({ resolver: zodResolver(tagSchema), defaultValues: { name: "", color: "" } });
  const submit = (data: TagFormData) => createTag.mutate(data, { onSuccess: () => reset() });
  return <section className="mt-6 border-t pt-4"><h2 className="mb-2 text-sm font-semibold">Tags</h2><form className="flex gap-2" onSubmit={handleSubmit(submit)}><Input aria-label="Tag name" placeholder="New tag" {...register("name")} /><Input aria-label="Tag color" placeholder="Color (optional)" {...register("color")} /><Button type="submit" disabled={createTag.isPending}>Add</Button></form>{errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}{errors.color && <p className="text-sm text-destructive">{errors.color.message}</p>}<ul className="mt-3 space-y-2">{tags.map((tag) => <li className="flex items-center gap-2" key={tag.id}><span className="rounded px-2 py-1 text-xs" style={{ backgroundColor: tag.color ?? undefined }}>{tag.name}</span><Button type="button" variant="ghost" size="sm" onClick={() => { const name = window.prompt("Tag name", tag.name); if (name) updateTag.mutate({ id: tag.id, name }); }}>Rename</Button><Button type="button" variant="ghost" size="sm" onClick={() => deleteTag.mutate(tag.id)}>Delete</Button></li>)}</ul></section>;
}
