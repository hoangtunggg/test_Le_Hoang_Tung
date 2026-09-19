import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Pencil, Trash2 } from "lucide-react";
import type { Todo } from "../api/todos";
import type { Tag } from "../api/todos";

interface TodoItemProps {
  todo: Todo;
  onToggle: (todo: Todo) => void;
  onEdit: (todo: Todo) => void;
  onDelete: (id: string) => void;
  selected: boolean;
  onSelect: (selected: boolean) => void;
  availableTags: Tag[];
  onAttach: (tagId: string) => void;
}

export function TodoItem({ todo, onToggle, onEdit, onDelete, selected, onSelect, availableTags, onAttach }: TodoItemProps) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors group">
      <Checkbox aria-label={`Select ${todo.title}`} checked={selected} onCheckedChange={(value) => onSelect(value === true)} />
      <Checkbox
        id={`todo-${todo.id}`}
        checked={todo.completed}
        onCheckedChange={() => onToggle(todo)}
      />

      <div className="flex-1 min-w-0">
        <label
          htmlFor={`todo-${todo.id}`}
          className={`text-sm font-medium cursor-pointer ${
            todo.completed ? "line-through text-muted-foreground" : ""
          }`}
        >
          {todo.title}
        </label>
        {todo.description && (
          <p className="text-xs text-muted-foreground mt-0.5 truncate">
            {todo.description}
          </p>
        )}
        {(todo.tags ?? []).map((tag) => <span key={tag.id} className="mr-1 rounded px-1.5 py-0.5 text-xs" style={{ backgroundColor: tag.color ?? undefined }}>{tag.name}</span>)}
        <select aria-label={`Attach tag to ${todo.title}`} className="ml-2 text-xs" defaultValue="" onChange={(event) => { if (event.target.value) { onAttach(event.target.value); event.currentTarget.value = ""; } }}><option value="">Attach tag</option>{availableTags.filter((tag) => !(todo.tags ?? []).some((attached) => attached.id === tag.id)).map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}</select>
      </div>

      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => onEdit(todo)}
        >
          <Pencil className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-destructive hover:text-destructive"
          onClick={() => onDelete(todo.id)}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
