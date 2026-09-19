import { useState } from "react";
import { Plus, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { useBulkStatus, useTodos, type TodoFilters as Filters } from "../api/todos";
import { TodoList } from "./TodoList";
import { TodoForm } from "./TodoForm";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { TagManager } from "@/features/tags/components/TagManager";
import { TodoFilters } from "./TodoFilters";

export function TodoPage() {
  const emptyTodoFilters: Filters = { status: "all", tag_id: "", keyword: "", date_from: "", date_to: "", page: 1, page_size: 20 };
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [filters, setFilters] = useState<Filters>(emptyTodoFilters);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const { data, isLoading, error } = useTodos(filters);
  const bulkStatus = useBulkStatus();
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-muted/40">
      {/* Header */}
      <header className="bg-card border-b">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold">Todo App</h1>
            {user && (
              <p className="text-sm text-muted-foreground">{user.email}</p>
            )}
          </div>
          <Button variant="ghost" size="sm" onClick={logout}>
            <LogOut className="h-4 w-4 mr-2" />
            Logout
          </Button>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-3xl mx-auto px-4 py-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">My Todos</CardTitle>
            <Button size="sm" onClick={() => setShowCreateForm(true)}>
              <Plus className="h-4 w-4 mr-1" />
              Add Todo
            </Button>
          </CardHeader>
          <Separator />
          <CardContent className="pt-4">
            <TodoFilters filters={filters} onChange={setFilters} />
            {selectedIds.length > 0 && <div className="mb-3 flex gap-2"><Button size="sm" onClick={() => bulkStatus.mutate({ todo_ids: selectedIds, completed: true }, { onSuccess: () => setSelectedIds([]) })}>Mark completed</Button><Button size="sm" variant="outline" onClick={() => bulkStatus.mutate({ todo_ids: selectedIds, completed: false }, { onSuccess: () => setSelectedIds([]) })}>Mark active</Button></div>}
            {isLoading && (
              <div className="text-center py-12 text-muted-foreground">
                Loading todos...
              </div>
            )}

            {error && (
              <div className="text-center py-12 text-destructive">
                Failed to load todos. Please try again.
              </div>
            )}

            {data && <TodoList todos={data.items} selectedIds={selectedIds} onSelectionChange={setSelectedIds} />}

            {data && data.total > 0 && (
              <div className="mt-4 text-center text-sm text-muted-foreground">
                Showing {data.items.length} of {data.total} todos
              </div>
            )}
            <TagManager />
          </CardContent>
        </Card>
      </main>

      {/* Create Todo Dialog */}
      <TodoForm
        mode="create"
        open={showCreateForm}
        onClose={() => setShowCreateForm(false)}
      />
    </div>
  );
}
