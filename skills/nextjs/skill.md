---
name: nextjs
description: Use when building Next.js App Router pages, server and client components, fetching data in server components, configuring layouts and middleware, handling routing patterns, optimizing images and fonts, or deploying a Next.js application.
---

# Next.js App Router

Patterns for building production Next.js applications with the App Router — server components, data fetching, routing, middleware, and performance.

## When to Activate

- Building or refactoring pages using the App Router (`app/` directory)
- Choosing between Server Components and Client Components
- Fetching data in server components, route handlers, or server actions
- Configuring layouts, templates, loading states, or error boundaries
- Implementing dynamic routes, catch-all segments, or parallel routes
- Setting up middleware for auth, redirects, or A/B testing
- Optimizing images, fonts, or bundle size for Core Web Vitals

---

## Server vs. Client Components

This is the most important decision in App Router — default to Server, opt into Client only when needed.

| Capability | Server Component | Client Component |
|---|---|---|
| Async / await at component level | Yes | No |
| Access database, secrets, fs | Yes | No |
| `useState`, `useEffect`, hooks | No | Yes |
| Event handlers (`onClick`, etc.) | No | Yes |
| Browser APIs | No | Yes |
| Rendered on | Server only | Server (initial) + Client |
| Bundle size impact | Zero JS sent | Adds to JS bundle |

```tsx
// BAD — making the whole page a Client Component just for one interactive part
"use client";
export default function Page() {
  const data = await fetchFromDB(); // ❌ can't await in client component
  return <div onClick={() => ...}>{data}</div>;
}

// GOOD — keep data fetching in Server Component, isolate interactivity
// app/page.tsx (Server Component — no directive needed)
export default async function Page() {
  const data = await fetchFromDB();
  return <div><InteractiveWidget data={data} /></div>;
}

// components/interactive-widget.tsx
"use client";
export function InteractiveWidget({ data }: { data: Data }) {
  const [open, setOpen] = useState(false);
  return <button onClick={() => setOpen(!open)}>{data.title}</button>;
}
```

**Push `"use client"` as far down the tree as possible.**

---

## Routing

### File Conventions

```
app/
  layout.tsx           — root layout (required)
  page.tsx             — route segment UI
  loading.tsx          — Suspense boundary fallback
  error.tsx            — error boundary ("use client" required)
  not-found.tsx        — 404 UI
  route.ts             — API route handler

  (auth)/              — route group (no URL segment)
    login/page.tsx     — /login
    register/page.tsx  — /register

  blog/
    [slug]/page.tsx    — /blog/any-slug
    [...slug]/page.tsx — /blog/a/b/c (catch-all)
    [[...slug]]/       — optional catch-all

  @modal/              — parallel route slot (named outlet)
```

### Dynamic Routes

```tsx
// app/blog/[slug]/page.tsx
interface Props {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ page?: string }>;
}

export default async function BlogPost({ params, searchParams }: Props) {
  const { slug } = await params;
  const { page = "1" } = await searchParams;
  const post = await getPost(slug);
  if (!post) notFound();
  return <article>{post.content}</article>;
}

// Static generation — provide all known slugs at build time
export async function generateStaticParams() {
  const posts = await getAllPosts();
  return posts.map((p) => ({ slug: p.slug }));
}
```

### Route Groups and Layouts

```
app/
  (marketing)/
    layout.tsx   — marketing shell (nav + footer)
    page.tsx     — /
    about/page.tsx — /about

  (app)/
    layout.tsx   — app shell (sidebar + auth check)
    dashboard/page.tsx — /dashboard
    settings/page.tsx  — /settings
```

Route groups let multiple layouts share the same URL namespace without polluting the URL.

---

## Data Fetching

### Server Component Fetch (preferred)

```tsx
// Fetch runs on the server — secrets never reach the browser
export default async function ProductList() {
  const products = await fetch("https://api.example.com/products", {
    next: { revalidate: 60 },   // ISR: revalidate every 60 seconds
    // next: { tags: ["products"] }  — on-demand revalidation
    // cache: "no-store"            — always fresh (SSR)
    // cache: "force-cache"         — static (default)
  }).then((r) => r.json());

  return <ul>{products.map((p) => <li key={p.id}>{p.name}</li>)}</ul>;
}
```

### Parallel Data Fetching

```tsx
// BAD — sequential, slow
const user = await getUser(id);
const posts = await getPosts(id); // waits for user first

// GOOD — parallel
const [user, posts] = await Promise.all([getUser(id), getPosts(id)]);
```

### Caching Strategy

| Need | Cache option | Revalidation |
|---|---|---|
| Static content (rarely changes) | `force-cache` (default) | `revalidatePath` / `revalidateTag` |
| Frequently updated | `next: { revalidate: N }` | Time-based ISR |
| Always live | `cache: "no-store"` | None — fetched every request |
| Per-user data | `cache: "no-store"` + auth header | None |

### Server Actions

```tsx
// app/actions.ts
"use server";

import { revalidatePath } from "next/cache";

export async function createPost(formData: FormData) {
  const title = formData.get("title") as string;
  await db.post.create({ data: { title } });
  revalidatePath("/blog");  // bust cache after mutation
}

// app/new-post/page.tsx (Server Component)
import { createPost } from "../actions";

export default function NewPostPage() {
  return (
    <form action={createPost}>
      <input name="title" />
      <button type="submit">Create</button>
    </form>
  );
}
```

---

## Route Handlers (API Routes)

```ts
// app/api/users/route.ts
import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const page = Number(searchParams.get("page") ?? 1);
  const users = await getUsers(page);
  return NextResponse.json(users);
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const user = await createUser(body);
  return NextResponse.json(user, { status: 201 });
}

// app/api/users/[id]/route.ts
export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  await deleteUser(id);
  return new NextResponse(null, { status: 204 });
}
```

---

## Middleware

```ts
// middleware.ts (runs on the Edge — no Node.js APIs)
import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  const token = request.cookies.get("session")?.value;

  if (!token && request.nextUrl.pathname.startsWith("/dashboard")) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/settings/:path*"],
};
```

---

## Metadata and SEO

```tsx
// app/blog/[slug]/page.tsx
import type { Metadata } from "next";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const post = await getPost(slug);
  return {
    title: post.title,
    description: post.excerpt,
    openGraph: {
      title: post.title,
      images: [post.coverImage],
    },
  };
}
```

---

## Image and Font Optimization

```tsx
// Images — always use next/image for automatic optimization
import Image from "next/image";

<Image
  src="/hero.jpg"
  alt="Hero"
  width={1200}
  height={630}
  priority            // LCP image — load eagerly
  placeholder="blur"
/>

// Remote images require config
// next.config.ts
const config = {
  images: {
    remotePatterns: [{ protocol: "https", hostname: "cdn.example.com" }],
  },
};

// Fonts — use next/font for zero-layout-shift loading
import { Inter } from "next/font/google";

const inter = Inter({ subsets: ["latin"], display: "swap" });

export default function RootLayout({ children }) {
  return <html className={inter.className}>{children}</html>;
}
```

---

## Loading and Error States

```tsx
// app/dashboard/loading.tsx — automatic Suspense boundary
export default function Loading() {
  return <DashboardSkeleton />;
}

// app/dashboard/error.tsx — must be a Client Component
"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <div>
      <p>Something went wrong: {error.message}</p>
      <button onClick={reset}>Try again</button>
    </div>
  );
}
```

---

## Environment Variables

| Variable prefix | Available in | Use for |
|---|---|---|
| `NEXT_PUBLIC_*` | Server + browser | Public config (API URLs, feature flags) |
| No prefix | Server only | Secrets, DB URLs, API keys |

```ts
// Safe — server-only
const dbUrl = process.env.DATABASE_URL;

// Exposed to browser — only for non-sensitive values
const apiUrl = process.env.NEXT_PUBLIC_API_URL;
```

Never put secrets in `NEXT_PUBLIC_*` variables — they are inlined into the client bundle.

---

## Red Flags

- **`"use client"` on a page or layout** — turns the entire subtree into client-side JS; push it down to the specific interactive component instead.
- **Fetching data inside Client Components with `useEffect`** — causes a client-side waterfall; fetch in a Server Component and pass data as props or use a Server Action.
- **Storing secrets in `NEXT_PUBLIC_*` env vars** — these are inlined into the browser bundle and visible to anyone.
- **Sequential `await` for independent data** — use `Promise.all` to fetch in parallel; sequential awaits multiply latency.
- **Using `<img>` instead of `next/image`** — misses automatic format conversion, lazy loading, and size optimization that directly affect CWV scores.
- **Putting everything in the root layout** — per-section layouts exist for a reason; a massive root layout re-renders on every navigation and bloats every page.
- **Ignoring `generateStaticParams`** — dynamic routes default to runtime rendering; add `generateStaticParams` for known paths to get static generation.
- **Route handlers for data the server already has** — calling your own API from a Server Component adds unnecessary network overhead; query the database directly.

---

## Checklist

- [ ] `"use client"` is at the leaf of the component tree — no unnecessary client boundaries higher up
- [ ] Independent data fetches run with `Promise.all`, not sequential `await`
- [ ] Cache strategy chosen explicitly: `force-cache`, `revalidate`, or `no-store` — not left to default accidentally
- [ ] Server Actions used for mutations — no separate API route just for form submissions
- [ ] Secrets stored in un-prefixed env vars — nothing sensitive in `NEXT_PUBLIC_*`
- [ ] `next/image` used for all `<img>` elements — width, height, and `alt` provided
- [ ] `next/font` used for web fonts — no `<link>` tags loading fonts in `<head>`
- [ ] `generateMetadata` exported from every public-facing page
- [ ] `generateStaticParams` added for dynamic routes with known paths
- [ ] `loading.tsx` and `error.tsx` present for routes with async data
- [ ] Middleware `matcher` is as narrow as possible — not running on static assets
- [ ] Route groups used to scope layouts — no monolithic root layout doing too much
