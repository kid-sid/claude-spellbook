---
name: frontend
description: Frontend patterns covering React component design, state management (Zustand/Redux Toolkit/Context), data fetching (TanStack Query), forms (React Hook Form + Zod), routing, performance optimization, and testing.
---

# Frontend Patterns

Conventions and best practices for building maintainable, performant React applications.

## When to Activate

- Designing component structure or deciding where state should live
- Choosing between local state, Context, Zustand, or Redux Toolkit
- Implementing data fetching, caching, or server state synchronization
- Building forms with validation and submission handling
- Optimizing rendering performance (re-renders, bundle size, lazy loading)
- Setting up routing with protected routes or nested layouts
- Writing tests for React components and hooks

## Component Design

### Single Responsibility

```tsx
// BAD: component does too many things
function UserDashboard({ userId }: { userId: string }) {
  const [user, setUser] = useState(null);
  const [orders, setOrders] = useState([]);
  useEffect(() => { /* fetch user + orders */ }, []);
  return <div>{/* render user, orders, sidebar, notifications */}</div>;
}

// GOOD: split by concern
function UserDashboard({ userId }: { userId: string }) {
  return (
    <DashboardLayout>
      <UserProfile userId={userId} />
      <OrderList userId={userId} />
      <NotificationPanel userId={userId} />
    </DashboardLayout>
  );
}
```

### Composition over Props Drilling

```tsx
// BAD: prop drilling through 3+ levels
<Page user={user} onLogout={onLogout} theme={theme} />
  <Header user={user} onLogout={onLogout} theme={theme} />
    <Nav user={user} onLogout={onLogout} theme={theme} />

// GOOD: compound component or slot pattern
<Page>
  <Header>
    <Nav />
    <UserMenu />
  </Header>
  <main>{children}</main>
</Page>
```

### Container / Presentational Split

```tsx
// Container: owns data fetching and state
function OrderListContainer({ userId }: { userId: string }) {
  const { data, isLoading, error } = useOrders(userId);
  if (isLoading) return <OrderListSkeleton />;
  if (error) return <ErrorBoundary error={error} />;
  return <OrderList orders={data} />;
}

// Presentational: pure rendering, easily testable
function OrderList({ orders }: { orders: Order[] }) {
  return (
    <ul>
      {orders.map(o => <OrderItem key={o.id} order={o} />)}
    </ul>
  );
}
```

## State Management

### Decision Matrix

| State Type | Tool | Examples |
|---|---|---|
| UI / ephemeral | `useState` / `useReducer` | modal open, input value, toggle |
| Shared UI state | Zustand or Context | theme, sidebar collapsed, selected tab |
| Server state | TanStack Query | API responses, lists, detail pages |
| Complex client state | Redux Toolkit | shopping cart, multi-step wizard, offline queue |
| URL state | Search params | filters, pagination, selected item |
| Form state | React Hook Form | field values, validation, submission |

### Zustand (preferred for shared UI state)

```tsx
import { create } from "zustand";

interface SidebarStore {
  isOpen: boolean;
  toggle: () => void;
  open: () => void;
  close: () => void;
}

const useSidebarStore = create<SidebarStore>((set) => ({
  isOpen: false,
  toggle: () => set((s) => ({ isOpen: !s.isOpen })),
  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
}));

// With persistence
import { persist } from "zustand/middleware";
const useThemeStore = create(persist(
  (set) => ({ theme: "light", setTheme: (t) => set({ theme: t }) }),
  { name: "theme-storage" },
));
```

### Redux Toolkit (complex client state)

```tsx
import { createSlice, createAsyncThunk } from "@reduxjs/toolkit";

const fetchOrders = createAsyncThunk("orders/fetch", async (userId: string) => {
  const res = await fetch(`/api/users/${userId}/orders`);
  return res.json();
});

const ordersSlice = createSlice({
  name: "orders",
  initialState: { items: [] as Order[], status: "idle" as LoadingStatus },
  reducers: {
    removeOrder: (state, action) => {
      state.items = state.items.filter(o => o.id !== action.payload);
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchOrders.pending, (state) => { state.status = "loading"; })
      .addCase(fetchOrders.fulfilled, (state, action) => {
        state.status = "succeeded";
        state.items = action.payload;
      })
      .addCase(fetchOrders.rejected, (state) => { state.status = "failed"; });
  },
});
```

## Data Fetching

### TanStack Query (server state)

```tsx
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

// Fetching
function useOrders(userId: string) {
  return useQuery({
    queryKey: ["orders", userId],
    queryFn: () => fetchOrders(userId),
    staleTime: 5 * 60 * 1000,  // 5 min — don't refetch if fresh
    gcTime: 10 * 60 * 1000,    // 10 min — keep in cache after unmount
  });
}

// Mutation with optimistic update
function useCancelOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (orderId: string) => cancelOrder(orderId),
    onMutate: async (orderId) => {
      await queryClient.cancelQueries({ queryKey: ["orders"] });
      const prev = queryClient.getQueryData(["orders"]);
      queryClient.setQueryData(["orders"], (old: Order[]) =>
        old.filter(o => o.id !== orderId),
      );
      return { prev };
    },
    onError: (_, __, ctx) => {
      queryClient.setQueryData(["orders"], ctx?.prev);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["orders"] }),
  });
}
```

### Query Key Conventions

```tsx
// Hierarchical keys enable targeted invalidation
["users"]                          // all users
["users", userId]                  // one user
["users", userId, "orders"]        // user's orders
["users", userId, "orders", { status: "active" }]  // filtered

queryClient.invalidateQueries({ queryKey: ["users", userId] });
// ^ invalidates user + all sub-keys (orders, profile, etc.)
```

## Forms

### React Hook Form + Zod

```tsx
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const schema = z.object({
  email: z.string().email("Invalid email"),
  password: z.string().min(8, "At least 8 characters"),
  role: z.enum(["admin", "user"]),
});

type FormValues = z.infer<typeof schema>;

function CreateUserForm() {
  const { register, handleSubmit, formState: { errors, isSubmitting } } =
    useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormValues) => {
    await createUser(data);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register("email")} />
      {errors.email && <p>{errors.email.message}</p>}
      <input type="password" {...register("password")} />
      {errors.password && <p>{errors.password.message}</p>}
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Creating…" : "Create User"}
      </button>
    </form>
  );
}
```

## Routing (React Router v6)

### Nested Layouts with Protected Routes

```tsx
import { createBrowserRouter, RouterProvider, Outlet, Navigate } from "react-router-dom";

function RequireAuth() {
  const { user } = useAuth();
  return user ? <Outlet /> : <Navigate to="/login" replace />;
}

const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,   // persistent layout (nav, sidebar)
        children: [
          { path: "/", element: <Dashboard /> },
          { path: "/orders", element: <OrderList /> },
          { path: "/orders/:id", element: <OrderDetail />,
            loader: ({ params }) => fetchOrder(params.id!) },
        ],
      },
    ],
  },
]);
```

### URL State for Filters

```tsx
import { useSearchParams } from "react-router-dom";

function OrderFilters() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "all";

  return (
    <select value={status} onChange={e =>
      setParams(p => { p.set("status", e.target.value); return p; })
    }>
      <option value="all">All</option>
      <option value="active">Active</option>
    </select>
  );
}
```

## Performance

### Memoization — when it helps

```tsx
// useMemo: expensive derivation, stable reference for children
const sortedOrders = useMemo(
  () => [...orders].sort((a, b) => b.total - a.total),
  [orders],
);

// useCallback: stable reference passed to memo'd child or as dep
const handleCancel = useCallback((id: string) => cancelOrder(id), [cancelOrder]);

// memo: skip re-render when props unchanged
const OrderItem = memo(function OrderItem({ order }: { order: Order }) {
  return <li>{order.id}</li>;
});

// BAD: wrapping everything — memo adds overhead, only helps when re-renders are expensive
```

### Code Splitting

```tsx
import { lazy, Suspense } from "react";

// Route-level splitting (most impactful)
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Reports = lazy(() => import("./pages/Reports"));

function App() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/reports" element={<Reports />} />
      </Routes>
    </Suspense>
  );
}
```

### Virtualization for Long Lists

```tsx
import { useVirtualizer } from "@tanstack/react-virtual";

function VirtualOrderList({ orders }: { orders: Order[] }) {
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: orders.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 64,
  });

  return (
    <div ref={parentRef} style={{ height: "600px", overflow: "auto" }}>
      <div style={{ height: virtualizer.getTotalSize() }}>
        {virtualizer.getVirtualItems().map(item => (
          <div key={item.key} style={{ transform: `translateY(${item.start}px)` }}>
            <OrderItem order={orders[item.index]} />
          </div>
        ))}
      </div>
    </div>
  );
}
```

## Testing

### Component Tests (React Testing Library)

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

test("submits form with valid data", async () => {
  const user = userEvent.setup();
  const onSubmit = vi.fn();
  render(<CreateUserForm onSubmit={onSubmit} />);

  await user.type(screen.getByLabelText("Email"), "alice@example.com");
  await user.type(screen.getByLabelText("Password"), "secretpass");
  await user.click(screen.getByRole("button", { name: "Create User" }));

  await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({
    email: "alice@example.com",
    password: "secretpass",
  }));
});

test("shows validation errors", async () => {
  const user = userEvent.setup();
  render(<CreateUserForm onSubmit={vi.fn()} />);

  await user.click(screen.getByRole("button", { name: "Create User" }));
  expect(await screen.findByText("Invalid email")).toBeInTheDocument();
});
```

### Testing Hooks

```tsx
import { renderHook, act } from "@testing-library/react";

test("useCounter increments", () => {
  const { result } = renderHook(() => useCounter(0));
  act(() => result.current.increment());
  expect(result.current.count).toBe(1);
});
```

> See also: `unit-testing`, `accessibility`

## Checklist

- [ ] Components have a single clear responsibility — split if rendering + fetching + formatting
- [ ] Server state managed with TanStack Query, not `useEffect` + `useState`
- [ ] Forms use React Hook Form with Zod schema validation
- [ ] Shared client state uses Zustand (simple) or Redux Toolkit (complex)
- [ ] URL state (filters, pagination, selected ID) stored in search params
- [ ] Route-level code splitting applied to all page components
- [ ] Lists over ~100 items virtualized
- [ ] `useMemo` / `useCallback` / `memo` applied only where profiling confirms re-render cost
- [ ] Components tested via React Testing Library (user interactions, not implementation)
- [ ] Accessible: semantic HTML, labels on inputs, keyboard navigation verified
- [ ] No prop drilling beyond 2 levels — use composition, Context, or Zustand
