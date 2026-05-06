---
name: typescript
description: Use when writing advanced TypeScript — creating utility types, narrowing unions, resolving tricky type errors, configuring the compiler for strict mode, building branded types, or augmenting third-party module types.
---

# TypeScript — Advanced Type Patterns

Deep TypeScript patterns for writing expressive, safe, self-documenting code.

## When to Activate

- Designing generic utilities, API clients, or typed event systems
- Using `infer`, conditional types, or mapped types
- Narrowing union types safely without casting
- Configuring `tsconfig.json` for strict mode or path aliases
- Augmenting third-party module types
- Building branded/nominal types for domain values

---

## Utility Types (Built-in)

```typescript
interface User {
  id: string;
  name: string;
  email: string;
  role: "admin" | "user";
  createdAt: Date;
}

// Partial — all fields optional
type UpdateUserDto = Partial<User>;

// Required — all fields required (reverse of Partial)
type FullUser = Required<Partial<User>>;

// Pick — select specific fields
type UserSummary = Pick<User, "id" | "name">;

// Omit — exclude specific fields
type CreateUserDto = Omit<User, "id" | "createdAt">;

// Readonly — immutable
type FrozenUser = Readonly<User>;

// Record — typed map
type RolePermissions = Record<User["role"], string[]>;
// equivalent to: { admin: string[]; user: string[] }

// Extract / Exclude — filter union members
type AdminRole = Extract<User["role"], "admin">;   // "admin"
type NonAdmin = Exclude<User["role"], "admin">;    // "user"

// NonNullable — remove null and undefined
type SafeId = NonNullable<string | null | undefined>;  // string

// ReturnType / Parameters — extract from function types
type Handler = (req: Request, res: Response) => void;
type HandlerReturn = ReturnType<Handler>;       // void
type HandlerParams = Parameters<Handler>;       // [Request, Response]

// Awaited — unwrap Promise
type Resolved = Awaited<Promise<Promise<string>>>;  // string
```

---

## Generics

```typescript
// Constrained generics
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key];
}
const name = getProperty(user, "name");  // string — fully typed

// Generic with default
interface ApiResponse<T = unknown> {
  data: T;
  status: number;
  message: string;
}

// Generic class
class Stack<T> {
  private items: T[] = [];
  push(item: T): void { this.items.push(item); }
  pop(): T | undefined { return this.items.pop(); }
  peek(): T | undefined { return this.items.at(-1); }
}

// Multiple type parameters
function zip<A, B>(as: A[], bs: B[]): [A, B][] {
  return as.map((a, i) => [a, bs[i]]);
}

// Infer — extract type from another type
type UnpackPromise<T> = T extends Promise<infer U> ? U : T;
type UnpackArray<T> = T extends (infer U)[] ? U : T;

type A = UnpackPromise<Promise<string>>;   // string
type B = UnpackArray<User[]>;             // User
```

---

## Conditional Types

```typescript
// Basic conditional
type IsString<T> = T extends string ? true : false;

// Distributive — applies to each union member
type Flatten<T> = T extends (infer U)[] ? U : T;
type F = Flatten<string[] | number | boolean[]>;  // string | number | boolean

// Non-distributive (wrap in tuple)
type IsEqual<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false;

// Extract function return type (reimplementing ReturnType)
type MyReturnType<T> = T extends (...args: any[]) => infer R ? R : never;

// Deep partial
type DeepPartial<T> = T extends object
  ? { [K in keyof T]?: DeepPartial<T[K]> }
  : T;

// Make specific keys required
type RequiredKeys<T, K extends keyof T> = Omit<T, K> & Required<Pick<T, K>>;

type UserWithRequiredEmail = RequiredKeys<Partial<User>, "email">;
// email is required, everything else optional
```

---

## Mapped Types

```typescript
// Basic mapped type
type Optional<T> = { [K in keyof T]?: T[K] };
type Nullable<T>  = { [K in keyof T]: T[K] | null };
type Stringify<T> = { [K in keyof T]: string };

// Remapping keys with as
type Getters<T> = {
  [K in keyof T as `get${Capitalize<string & K>}`]: () => T[K];
};
type UserGetters = Getters<User>;
// { getId: () => string; getName: () => string; ... }

// Filter keys by value type
type PickByValue<T, V> = {
  [K in keyof T as T[K] extends V ? K : never]: T[K];
};
type StringFields = PickByValue<User, string>;
// { id: string; name: string; email: string }

// Mutable (remove readonly)
type Mutable<T> = { -readonly [K in keyof T]: T[K] };

// Required (remove optional)
type DefinedFields<T> = { [K in keyof T]-?: T[K] };
```

---

## Template Literal Types

```typescript
type EventName = "click" | "focus" | "blur";
type HandlerName = `on${Capitalize<EventName>}`;
// "onClick" | "onFocus" | "onBlur"

type CSSProperty = "margin" | "padding";
type CSSDirection = "Top" | "Right" | "Bottom" | "Left";
type CSSLonghand = `${CSSProperty}${CSSDirection}`;
// "marginTop" | "marginRight" | ... | "paddingLeft"

// Route parameter extraction
type ExtractRouteParams<T extends string> =
  T extends `${string}:${infer Param}/${infer Rest}`
    ? Param | ExtractRouteParams<`/${Rest}`>
    : T extends `${string}:${infer Param}`
    ? Param
    : never;

type Params = ExtractRouteParams<"/users/:userId/orders/:orderId">;
// "userId" | "orderId"

// Typed event emitter
type EventMap = {
  "user:created": { id: string; email: string };
  "user:deleted": { id: string };
  "order:placed": { orderId: string; total: number };
};

declare function on<K extends keyof EventMap>(
  event: K,
  handler: (payload: EventMap[K]) => void,
): void;

on("user:created", ({ id, email }) => { ... });  // fully typed payload
```

---

## Discriminated Unions

The most important pattern for modeling states that must not be mixed.

```typescript
// Each variant has a literal "type" field — TypeScript narrows on it
type ApiState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: string };

function render<T>(state: ApiState<T>) {
  switch (state.status) {
    case "idle":    return "Waiting...";
    case "loading": return "Loading...";
    case "success": return state.data;   // T — TypeScript knows data exists here
    case "error":   return state.error;  // string — TypeScript knows error exists
  }
}

// Result type pattern (no exceptions)
type Result<T, E = Error> =
  | { ok: true;  value: T }
  | { ok: false; error: E };

async function fetchUser(id: string): Promise<Result<User>> {
  try {
    const user = await db.findUser(id);
    return { ok: true, value: user };
  } catch (e) {
    return { ok: false, error: e as Error };
  }
}

const result = await fetchUser("123");
if (result.ok) {
  console.log(result.value.name);  // User
} else {
  console.error(result.error.message);  // Error
}
```

---

## Type Narrowing

```typescript
// typeof
function process(val: string | number) {
  if (typeof val === "string") val.toUpperCase();  // string here
  else val.toFixed(2);                             // number here
}

// instanceof
function handle(err: unknown) {
  if (err instanceof Error)    console.error(err.message);
  if (err instanceof TypeError) console.error("Type error:", err.message);
}

// in — check property existence
type Cat = { meow: () => void };
type Dog = { bark: () => void };
function makeSound(animal: Cat | Dog) {
  if ("meow" in animal) animal.meow();
  else animal.bark();
}

// Custom type guard
function isUser(value: unknown): value is User {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    "email" in value
  );
}

// Assertion function
function assertDefined<T>(val: T | null | undefined): asserts val is T {
  if (val == null) throw new Error("Expected value to be defined");
}

assertDefined(user);
user.name;  // TypeScript knows user is not null/undefined after this line
```

---

## `satisfies` Operator (TypeScript 4.9+)

Validates a value matches a type without widening the inferred type.

```typescript
const palette = {
  red:   [255, 0, 0],
  green: "#00ff00",
  blue:  [0, 0, 255],
} satisfies Record<string, string | number[]>;

// Without satisfies: palette.red would be string | number[]
// With satisfies:    palette.red is number[] — inferred type is preserved
palette.red.map(v => v * 2);   // ✅ TypeScript knows it's number[]
palette.green.toUpperCase();   // ✅ TypeScript knows it's string
```

---

## Branded / Nominal Types

Prevent mixing semantically different `string` values at compile time.

```typescript
type Brand<T, B extends string> = T & { readonly __brand: B };

type UserId  = Brand<string, "UserId">;
type OrderId = Brand<string, "OrderId">;

function createUserId(id: string): UserId {
  return id as UserId;
}

function getUser(id: UserId): User { ... }

const userId  = createUserId("abc-123");
const orderId = "xyz-456" as OrderId;

getUser(userId);   // ✅
getUser(orderId);  // ❌ TypeScript error — OrderId is not UserId
getUser("raw");    // ❌ TypeScript error — string is not UserId
```

---

## Declaration Merging and Module Augmentation

```typescript
// Extend an existing interface (e.g. Express Request)
declare global {
  namespace Express {
    interface Request {
      user?: User;
      requestId: string;
    }
  }
}

// Augment a third-party module
declare module "some-library" {
  interface SomeClass {
    myCustomMethod(): void;
  }
}

// Extend Window
declare global {
  interface Window {
    analytics: AnalyticsInstance;
  }
}
```

---

## tsconfig.json (Strict Setup)

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "lib": ["ES2022", "DOM"],

    // Strict mode — enable all of these
    "strict": true,
    "noUncheckedIndexedAccess": true,   // arr[i] is T | undefined
    "exactOptionalPropertyTypes": true, // optional ≠ undefined
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,

    // Output
    "outDir": "./dist",
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,

    // Paths (monorepo / aliases)
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@shared/*": ["../shared/src/*"]
    },

    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

---

## Common Patterns

```typescript
// Exhaustive check — compiler error if a union case is missed
function assertNever(x: never): never {
  throw new Error(`Unhandled case: ${JSON.stringify(x)}`);
}

switch (status) {
  case "active":   return handleActive();
  case "inactive": return handleInactive();
  default:         return assertNever(status);  // error if new status added
}

// Readonly deep freeze
function freeze<T>(obj: T): Readonly<T> {
  return Object.freeze(obj);
}

// Builder pattern with method chaining
class QueryBuilder<T> {
  private filters: Partial<T> = {};

  where<K extends keyof T>(key: K, value: T[K]): this {
    this.filters[key] = value;
    return this;
  }

  build(): Partial<T> { return this.filters; }
}

// Const assertion
const ROUTES = {
  home:    "/",
  users:   "/users",
  profile: "/profile",
} as const;

type Route = (typeof ROUTES)[keyof typeof ROUTES];
// "/" | "/users" | "/profile"
```

---

## Red Flags

- **`any` instead of `unknown` for external data** — `any` disables all type checking on a value and everything it touches; use `unknown` for data of uncertain shape and narrow it with type guards before use
- **Type assertions (`as`) instead of type guards** — `value as User` tells the compiler to trust you without verification; if the shape is wrong at runtime, you get silent data corruption rather than a type error; use `isUser(value)` type guards
- **`// @ts-ignore` or `// @ts-expect-error` as a long-term fix** — suppression comments hide real type problems; investigate the root cause and fix the types or the code
- **`strict: false` in tsconfig** — without strict mode, `null` and `undefined` escape into typed values silently; enable `strict: true` from project start; retrofitting it later costs weeks
- **Missing exhaustive check in `switch`/`match`** — a switch over a union without an `assertNever` default compiles successfully when a new union member is added, silently falling through; always add `assertNever(x)` in the default case
- **`noUncheckedIndexedAccess` disabled** — `arr[i]` returns `T` instead of `T | undefined`, hiding off-by-one errors; enable this flag and handle the `undefined` case explicitly
- **Widening an inferred type with an explicit annotation** — `const routes: string[] = ["/home", "/users"]` loses the literal types; use `as const` or `satisfies` to preserve precision while still validating the shape

## Checklist

- [ ] `strict: true` + `noUncheckedIndexedAccess` in tsconfig
- [ ] Discriminated unions used for state/result types instead of optional fields
- [ ] `satisfies` used when you want validation without losing inferred precision
- [ ] Branded types for domain IDs (`UserId`, `OrderId`) to prevent mix-ups
- [ ] `assertNever` used in switch/match exhaustive checks
- [ ] `unknown` used instead of `any` for external data; narrowed before use
- [ ] Type guards (`is`) and assertion functions (`asserts`) instead of casts
- [ ] `Readonly<T>` on function parameters that shouldn't be mutated
- [ ] Module augmentation in `.d.ts` files for third-party type extensions
