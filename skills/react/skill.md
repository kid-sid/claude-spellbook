---
name: react
description: Advanced React patterns — hooks deep dive, custom hooks, compound components, context design, error boundaries, Suspense, concurrent features, Next.js App Router (Server Components, Server Actions), and TypeScript with React. Complements the frontend skill which covers state management, data fetching, forms, routing, and testing.
---

# React — Advanced Patterns

> For state management (Zustand/Redux), TanStack Query, React Hook Form, React Router, and component testing, see the `frontend` skill.

## When to Activate

- Designing or debugging custom hooks
- Choosing between Context, Zustand, or prop drilling
- Using Suspense, error boundaries, or concurrent features (`useTransition`, `useDeferredValue`)
- Building compound components or headless/renderless components
- Working in Next.js App Router (Server Components, Server Actions, streaming)
- TypeScript generics, event types, or `forwardRef` patterns
- `useRef`, `useImperativeHandle`, portals, or advanced DOM integration

---

## Hooks Deep Dive

### useReducer — when useState gets complex

```tsx
type State = { count: number; error: string | null; loading: boolean };
type Action =
  | { type: "increment" }
  | { type: "set_error"; payload: string }
  | { type: "reset" };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "increment": return { ...state, count: state.count + 1 };
    case "set_error": return { ...state, error: action.payload, loading: false };
    case "reset":     return { count: 0, error: null, loading: false };
  }
}

const [state, dispatch] = useReducer(reducer, { count: 0, error: null, loading: false });
dispatch({ type: "increment" });
```

Use `useReducer` over `useState` when: multiple related state fields, next state depends on previous, or actions have semantic names that make logic readable.

### useRef — three distinct uses

```tsx
// 1. DOM access
const inputRef = useRef<HTMLInputElement>(null);
useEffect(() => { inputRef.current?.focus(); }, []);

// 2. Mutable value that doesn't trigger re-render (e.g. interval ID, previous value)
const timerRef = useRef<NodeJS.Timeout | null>(null);
const prevValueRef = useRef(value);
useEffect(() => { prevValueRef.current = value; });

// 3. Stable callback reference (avoids stale closure in event listeners)
const callbackRef = useRef(onSave);
useEffect(() => { callbackRef.current = onSave; });
useEffect(() => {
  const handler = () => callbackRef.current();
  window.addEventListener("keydown", handler);
  return () => window.removeEventListener("keydown", handler);
}, []); // dep array stays empty — no stale closure
```

### useContext — subscribe only to what you need

```tsx
// Split large contexts to prevent unnecessary re-renders
const UserDataContext = createContext<UserData | null>(null);
const UserActionsContext = createContext<UserActions | null>(null);

// Custom hook enforces non-null and co-locates error message
function useUserData() {
  const ctx = useContext(UserDataContext);
  if (!ctx) throw new Error("useUserData must be used inside UserProvider");
  return ctx;
}

// Provider combines both
function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserData | null>(null);
  const actions = useMemo(() => ({ login: ..., logout: ... }), []); // stable ref
  return (
    <UserDataContext.Provider value={user}>
      <UserActionsContext.Provider value={actions}>
        {children}
      </UserActionsContext.Provider>
    </UserDataContext.Provider>
  );
}
```

**Context is NOT a performance-free global store.** Every consumer re-renders when the value changes. Use Zustand for frequently-changing shared state; Context for stable config (theme, locale, auth user).

### Concurrent Features

```tsx
// useTransition — mark state update as non-urgent (keeps UI responsive)
const [isPending, startTransition] = useTransition();

function handleSearch(query: string) {
  setInputValue(query);              // urgent — update input immediately
  startTransition(() => {
    setFilteredResults(filter(query)); // non-urgent — can be interrupted
  });
}

// useDeferredValue — defer a derived value (use when you don't own the state setter)
const deferredQuery = useDeferredValue(searchQuery);
const results = useMemo(() => filter(deferredQuery), [deferredQuery]);
const isStale = searchQuery !== deferredQuery; // show loading indicator

// useId — stable unique IDs across server/client (avoids hydration mismatch)
function FormField({ label }: { label: string }) {
  const id = useId();
  return (
    <>
      <label htmlFor={id}>{label}</label>
      <input id={id} />
    </>
  );
}
```

---

## Custom Hooks

Extract logic into a hook when: the same `useEffect` + `useState` combo appears twice, or a component mixes UI with data-fetching concerns.

```tsx
// useLocalStorage — syncs state with localStorage
function useLocalStorage<T>(key: string, initialValue: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(key);
      return stored ? JSON.parse(stored) : initialValue;
    } catch {
      return initialValue;
    }
  });

  const set = useCallback((newValue: T | ((prev: T) => T)) => {
    setValue(prev => {
      const next = newValue instanceof Function ? newValue(prev) : newValue;
      localStorage.setItem(key, JSON.stringify(next));
      return next;
    });
  }, [key]);

  return [value, set] as const;
}

// useDebounce — delay reacting to fast-changing input
function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

// useEventListener — typed, auto-cleaned
function useEventListener<K extends keyof WindowEventMap>(
  event: K,
  handler: (e: WindowEventMap[K]) => void,
  element: EventTarget = window,
) {
  const handlerRef = useRef(handler);
  useEffect(() => { handlerRef.current = handler; });
  useEffect(() => {
    const fn = (e: Event) => handlerRef.current(e as WindowEventMap[K]);
    element.addEventListener(event, fn);
    return () => element.removeEventListener(event, fn);
  }, [event, element]);
}
```

---

## Compound Components

Let parent manage state; children access it via Context. No prop drilling, flexible composition.

```tsx
const TabsContext = createContext<{ active: string; setActive: (id: string) => void } | null>(null);
const useTabs = () => {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error("Must be used inside <Tabs>");
  return ctx;
};

function Tabs({ defaultTab, children }: { defaultTab: string; children: ReactNode }) {
  const [active, setActive] = useState(defaultTab);
  return (
    <TabsContext.Provider value={{ active, setActive }}>
      <div>{children}</div>
    </TabsContext.Provider>
  );
}

function Tab({ id, children }: { id: string; children: ReactNode }) {
  const { active, setActive } = useTabs();
  return (
    <button
      role="tab"
      aria-selected={active === id}
      onClick={() => setActive(id)}
    >
      {children}
    </button>
  );
}

function TabPanel({ id, children }: { id: string; children: ReactNode }) {
  const { active } = useTabs();
  return active === id ? <div role="tabpanel">{children}</div> : null;
}

Tabs.Tab = Tab;
Tabs.Panel = TabPanel;

// Usage
<Tabs defaultTab="overview">
  <Tabs.Tab id="overview">Overview</Tabs.Tab>
  <Tabs.Tab id="settings">Settings</Tabs.Tab>
  <Tabs.Panel id="overview"><OverviewContent /></Tabs.Panel>
  <Tabs.Panel id="settings"><SettingsContent /></Tabs.Panel>
</Tabs>
```

---

## Error Boundaries

React errors during render are caught by the nearest error boundary. Must be a class component (or use `react-error-boundary` library).

```tsx
import { ErrorBoundary } from "react-error-boundary";

function ErrorFallback({ error, resetErrorBoundary }: FallbackProps) {
  return (
    <div role="alert">
      <p>Something went wrong:</p>
      <pre>{error.message}</pre>
      <button onClick={resetErrorBoundary}>Try again</button>
    </div>
  );
}

// Wrap any subtree that might throw during render
<ErrorBoundary
  FallbackComponent={ErrorFallback}
  onReset={() => queryClient.resetQueries()}
  onError={(error, info) => logger.error(error, info)}
>
  <UserDashboard />
</ErrorBoundary>
```

Error boundaries do **not** catch: async errors (use `try/catch`), event handler errors, or server-side errors.

---

## Suspense

```tsx
// Suspense shows fallback while children are loading (lazy imports or data)
<Suspense fallback={<Spinner />}>
  <LazyComponent />
</Suspense>

// Nested Suspense — granular loading states
<Suspense fallback={<PageSkeleton />}>
  <PageHeader />
  <Suspense fallback={<TableSkeleton />}>
    <DataTable />        {/* streams in independently */}
  </Suspense>
</Suspense>

// Combine with ErrorBoundary
<ErrorBoundary FallbackComponent={ErrorFallback}>
  <Suspense fallback={<Spinner />}>
    <AsyncComponent />
  </Suspense>
</ErrorBoundary>
```

---

## forwardRef and useImperativeHandle

```tsx
// forwardRef — pass ref through to a DOM element
const Input = forwardRef<HTMLInputElement, InputProps>(function Input(props, ref) {
  return <input ref={ref} {...props} />;
});

// useImperativeHandle — expose a custom API instead of the raw DOM node
interface DialogHandle { open: () => void; close: () => void }

const Dialog = forwardRef<DialogHandle, DialogProps>(function Dialog(props, ref) {
  const [open, setOpen] = useState(false);
  useImperativeHandle(ref, () => ({
    open:  () => setOpen(true),
    close: () => setOpen(false),
  }));
  return open ? <div>{props.children}</div> : null;
});

// Usage
const dialogRef = useRef<DialogHandle>(null);
dialogRef.current?.open();
```

---

## Portals

Render outside the component tree (modals, tooltips, toasts) without CSS stacking-context issues.

```tsx
import { createPortal } from "react-dom";

function Modal({ children, onClose }: ModalProps) {
  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        {children}
      </div>
    </div>,
    document.body,   // renders at the bottom of <body>, outside the app root
  );
}
```

---

## TypeScript Patterns

```tsx
// Generic component
function List<T extends { id: string }>({
  items,
  renderItem,
}: {
  items: T[];
  renderItem: (item: T) => ReactNode;
}) {
  return <ul>{items.map(item => <li key={item.id}>{renderItem(item)}</li>)}</ul>;
}

// Event types
const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => setValue(e.target.value);
const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => { e.preventDefault(); ... };
const handleClick  = (e: React.MouseEvent<HTMLButtonElement>) => { ... };

// Polymorphic component (renders as any element)
type ButtonProps<T extends ElementType = "button"> = {
  as?: T;
  children: ReactNode;
} & ComponentPropsWithoutRef<T>;

function Button<T extends ElementType = "button">({ as, children, ...props }: ButtonProps<T>) {
  const Component = as ?? "button";
  return <Component {...props}>{children}</Component>;
}
// <Button as="a" href="/home">Go home</Button>

// Children utilities
type WithChildren<T = {}> = T & { children: ReactNode };
type WithOptionalChildren<T = {}> = T & { children?: ReactNode };
```

---

## Next.js App Router

### Server vs Client Components

```tsx
// Server Component (default) — runs on server, no hooks, no browser APIs
// app/users/page.tsx
export default async function UsersPage() {
  const users = await db.user.findMany();  // direct DB access — no API round-trip
  return <UserList users={users} />;
}

// Client Component — add "use client" directive, can use hooks
"use client";
import { useState } from "react";

export function SearchInput({ onSearch }: { onSearch: (q: string) => void }) {
  const [value, setValue] = useState("");
  return <input value={value} onChange={e => { setValue(e.target.value); onSearch(e.target.value); }} />;
}

// Pattern: Server Component wraps Client Component
// Server fetches data, Client handles interactivity
export default async function Page() {
  const initialData = await fetchData();
  return <InteractiveWidget initialData={initialData} />;  // Client Component
}
```

### Server Actions

```tsx
// app/actions.ts
"use server";
import { revalidatePath } from "next/cache";

export async function createUser(formData: FormData) {
  const name = formData.get("name") as string;
  await db.user.create({ data: { name } });
  revalidatePath("/users");  // bust the cache for this route
}

// Use directly in a Server Component form
<form action={createUser}>
  <input name="name" />
  <button type="submit">Create</button>
</form>

// Or call from a Client Component
"use client";
import { createUser } from "./actions";
import { useFormState, useFormStatus } from "react-dom";

function SubmitButton() {
  const { pending } = useFormStatus();
  return <button type="submit" disabled={pending}>{pending ? "Saving…" : "Save"}</button>;
}

export function UserForm() {
  const [state, action] = useFormState(createUser, null);
  return <form action={action}><SubmitButton /></form>;
}
```

### Streaming with Suspense

```tsx
// app/dashboard/page.tsx — stream slow sections independently
import { Suspense } from "react";

export default function DashboardPage() {
  return (
    <div>
      <PageHeader />                         {/* renders immediately */}
      <Suspense fallback={<StatsSkeleton />}>
        <SlowStats />                        {/* streams in when ready */}
      </Suspense>
      <Suspense fallback={<FeedSkeleton />}>
        <ActivityFeed />                     {/* streams independently */}
      </Suspense>
    </div>
  );
}
```

### Metadata and Caching

```tsx
// Static metadata
export const metadata: Metadata = { title: "Users", description: "Manage users" };

// Dynamic metadata
export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const user = await fetchUser(params.id);
  return { title: user.name };
}

// Fetch caching options
fetch(url, { cache: "no-store" });         // always fresh (SSR)
fetch(url, { next: { revalidate: 60 } });  // ISR — revalidate every 60 seconds
fetch(url);                                // default: cached (SSG)
```

---

## Common Pitfalls

| Pitfall | Fix |
|---|---|
| `useEffect` with missing deps | Add all deps; extract stable refs with `useRef` if needed |
| Stale closure in event listener | Store callback in `useRef`, reference in handler |
| Context re-rendering all consumers | Split into data + actions contexts; memoize value |
| `key` on wrong element | Put `key` on the outermost element returned by `map`, not inside it |
| Mutating state directly | Always return new object/array from `useState` setter |
| `async` in `useEffect` directly | Declare `async` inner function, call it immediately |
| Server Component importing Client Component that imports server-only code | Use `server-only` package or restructure imports |

---

## Checklist

- [ ] Custom hooks extracted for any logic reused across 2+ components
- [ ] Context split into data + actions to avoid unnecessary re-renders
- [ ] Error boundaries wrapping async/data-dependent subtrees
- [ ] `forwardRef` used when a parent needs a DOM ref to a child component
- [ ] `useTransition` wrapping non-urgent state updates (search, filter, navigation)
- [ ] Next.js: Server Components for data fetching, Client Components only for interactivity
- [ ] Next.js: Server Actions used for form mutations instead of API routes where possible
- [ ] TypeScript event types used (not `any`) on all event handlers

> See also: `frontend` (state management, TanStack Query, forms, routing, testing), `accessibility`
