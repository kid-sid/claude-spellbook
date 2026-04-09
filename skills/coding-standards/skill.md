---
name: coding-standards
description: "Code quality standards: naming conventions per language (Python/TypeScript/Go), SOLID principles with examples, design patterns quick reference (12 patterns, full code for Factory/Strategy/Observer/Repository), code smell catalog with refactoring directions, and language-specific idioms."
---

# Coding Standards

A comprehensive reference for writing clean, consistent, maintainable code across Python, TypeScript, and Go.

## When to Activate

- Reviewing a pull request for code quality
- Refactoring legacy or unclear code
- Naming a class, function, variable, or file
- Deciding which design pattern to apply
- Setting up coding standards for a new project
- Identifying code smells and their root causes

---

## Naming Conventions

| Construct | Python | TypeScript | Go |
|---|---|---|---|
| Variables | `snake_case` | `camelCase` | `camelCase` |
| Functions / methods | `snake_case` | `camelCase` | `PascalCase` (exported), `camelCase` (unexported) |
| Classes / types | `PascalCase` | `PascalCase` | `PascalCase` |
| Constants | `UPPER_SNAKE_CASE` | `UPPER_SNAKE_CASE` or `camelCase` | `PascalCase` (exported), `camelCase` (unexported) |
| Interfaces | N/A | `IFoo` (avoid) or just `Foo` (preferred) | `Foo` (no `I` prefix) |
| Files | `snake_case.py` | `kebab-case.ts` or `camelCase.ts` | `snake_case.go` |
| Test files | `test_*.py` | `*.test.ts` / `*.spec.ts` | `*_test.go` |

### Naming Heuristics

- Be specific: `user_registration_date` not `date`; `payment_amount_cents` not `amount`
- Avoid meaningless suffixes: `UserManager`, `DataHelper`, `Utils` — what does it manage/help/do?
- Boolean names: use `is_`, `has_`, `can_`, `should_` prefix: `is_active`, `has_permission`
- Functions: verb phrases — `calculate_tax()`, `send_email()`, `validate_schema()`
- Avoid abbreviations except universally understood ones (`id`, `url`, `http`, `db`)
- Length proportional to scope: loop variable `i` is fine; module-level variable needs a full name

```python
# BAD
def proc(d, f):
    temp = d * f
    return temp

# GOOD
def calculate_discounted_price(base_price: float, discount_factor: float) -> float:
    return base_price * discount_factor
```

---

## SOLID Principles

### S — Single Responsibility

A class should have one reason to change.

```typescript
// BAD — UserService does everything
class UserService {
  createUser(data: CreateUserDto) { /* ... */ }
  sendWelcomeEmail(user: User) { /* ... */ }  // email is a separate concern
  generateReport(users: User[]) { /* ... */ } // reporting is a separate concern
}

// GOOD — separated concerns
class UserService { createUser(data: CreateUserDto) { /* ... */ } }
class EmailService { sendWelcomeEmail(user: User) { /* ... */ } }
class UserReportService { generateReport(users: User[]) { /* ... */ } }
```

### O — Open/Closed

Open for extension, closed for modification.

```typescript
// BAD — must modify to add new discount type
function calculateDiscount(type: string, price: number): number {
  if (type === 'student') return price * 0.8;
  if (type === 'senior') return price * 0.75;
  // must add else-if here for each new type
}

// GOOD — extend by adding a new class
interface DiscountStrategy { apply(price: number): number; }
class StudentDiscount implements DiscountStrategy { apply(p: number) { return p * 0.8; } }
class SeniorDiscount implements DiscountStrategy { apply(p: number) { return p * 0.75; } }
```

### L — Liskov Substitution

Subtypes must be substitutable for their base type.

```typescript
// BAD — Square overrides setWidth/setHeight inconsistently, breaking Rectangle contract
class Rectangle {
  constructor(protected width: number, protected height: number) {}
  setWidth(w: number) { this.width = w; }
  setHeight(h: number) { this.height = h; }
  area() { return this.width * this.height; }
}
class Square extends Rectangle {
  setWidth(w: number) { this.width = this.height = w; }   // violates LSP
  setHeight(h: number) { this.width = this.height = h; }  // caller expects independent dims
}

// GOOD — model separately; share via interface if needed
interface Shape { area(): number; }
class Rectangle implements Shape {
  constructor(private w: number, private h: number) {}
  area() { return this.w * this.h; }
}
class Square implements Shape {
  constructor(private side: number) {}
  area() { return this.side * this.side; }
}
```

### I — Interface Segregation

Many specific interfaces are better than one general interface.

```typescript
// BAD — not all workers can eat or sleep
interface Worker { work(): void; eat(): void; sleep(): void; }

// GOOD — split by capability
interface Workable { work(): void; }
interface Feedable { eat(): void; }
interface Restable { sleep(): void; }

class HumanWorker implements Workable, Feedable, Restable {
  work() { /* ... */ }
  eat() { /* ... */ }
  sleep() { /* ... */ }
}
class RobotWorker implements Workable {
  work() { /* ... */ }
}
```

### D — Dependency Inversion

Depend on abstractions, not concretions.

```typescript
// BAD — tightly coupled to PostgresDB
class UserRepository {
  private db = new PostgresDB();  // concrete dependency
  find(id: string) { return this.db.query(/* ... */); }
}

// GOOD — depends on interface, injected
interface Database { query(sql: string, params: unknown[]): Promise<unknown[]>; }
class UserRepository {
  constructor(private db: Database) {}
  find(id: string) { return this.db.query('SELECT * FROM users WHERE id = $1', [id]); }
}
```

---

## Design Patterns Quick Reference

| Pattern | Category | One-line use case | When to avoid |
|---|---|---|---|
| Factory | Creational | Create objects without specifying concrete class | When you only have one type |
| Abstract Factory | Creational | Create families of related objects | Overkill for simple factories |
| Singleton | Creational | One shared instance (config, logger) | When it becomes global mutable state |
| Builder | Creational | Step-by-step construction of complex objects | Simple objects with few fields |
| Strategy | Behavioral | Swap algorithms at runtime | When you only have one algorithm |
| Observer | Behavioral | Notify dependents when state changes | When observers outlive the subject |
| Command | Behavioral | Encapsulate a request as an object (undo/redo) | Simple one-off calls |
| Template Method | Behavioral | Define skeleton, let subclasses fill steps | Deep inheritance hierarchies |
| Repository | Structural | Isolate data access from domain logic | When ORM already provides this |
| Adapter | Structural | Wrap incompatible interface | When both interfaces are yours (just fix one) |
| Decorator | Structural | Add behavior to objects dynamically | When subclassing is simpler |
| Facade | Structural | Simplified interface to complex subsystem | Over-used to hide bad design |

### Full Code Examples

#### Factory

```typescript
interface Logger { log(msg: string): void; }
class ConsoleLogger implements Logger { log(msg: string) { console.log(msg); } }
class FileLogger implements Logger { log(msg: string) { fs.appendFileSync('app.log', msg); } }

function createLogger(type: 'console' | 'file'): Logger {
  if (type === 'console') return new ConsoleLogger();
  return new FileLogger();
}

// Usage
const logger = createLogger('console');
logger.log('Server started');
```

#### Strategy

```typescript
interface SortStrategy { sort(data: number[]): number[]; }
class QuickSort implements SortStrategy { sort(d: number[]) { /* quicksort impl */ return d; } }
class MergeSort implements SortStrategy { sort(d: number[]) { /* mergesort impl */ return d; } }

class DataSorter {
  constructor(private strategy: SortStrategy) {}
  sort(data: number[]) { return this.strategy.sort(data); }
  setStrategy(strategy: SortStrategy) { this.strategy = strategy; }
}

// Swap strategy at runtime
const sorter = new DataSorter(new QuickSort());
sorter.setStrategy(new MergeSort());
sorter.sort([5, 3, 1, 4, 2]);
```

#### Observer

```typescript
type Listener<T> = (event: T) => void;

class EventEmitter<T> {
  private listeners: Listener<T>[] = [];
  subscribe(fn: Listener<T>) { this.listeners.push(fn); }
  unsubscribe(fn: Listener<T>) { this.listeners = this.listeners.filter(l => l !== fn); }
  emit(event: T) { this.listeners.forEach(fn => fn(event)); }
}

const orderEvents = new EventEmitter<{ orderId: string; status: string }>();
orderEvents.subscribe(({ orderId }) => sendConfirmationEmail(orderId));
orderEvents.subscribe(({ orderId }) => updateInventory(orderId));
orderEvents.emit({ orderId: '123', status: 'paid' });
```

#### Repository

```typescript
interface UserRepository {
  findById(id: string): Promise<User | null>;
  save(user: User): Promise<void>;
  delete(id: string): Promise<void>;
}

class PostgresUserRepository implements UserRepository {
  constructor(private db: Database) {}

  async findById(id: string): Promise<User | null> {
    const [row] = await this.db.query('SELECT * FROM users WHERE id = $1', [id]);
    return row ? User.fromRow(row) : null;
  }

  async save(user: User): Promise<void> {
    await this.db.query(
      'INSERT INTO users (id, email) VALUES ($1, $2) ON CONFLICT (id) DO UPDATE SET email = $2',
      [user.id, user.email]
    );
  }

  async delete(id: string): Promise<void> {
    await this.db.query('DELETE FROM users WHERE id = $1', [id]);
  }
}
```

---

## Code Smells Catalog

| Smell | Symptom | Refactoring |
|---|---|---|
| Long Method | Function > 30 lines | Extract Method |
| Long Class / God Class | Class > 300 lines or too many responsibilities | Extract Class |
| Data Clump | Same 3+ params appear together everywhere | Introduce Parameter Object |
| Primitive Obsession | Using strings/ints for domain concepts (money, email) | Introduce Value Object |
| Feature Envy | Method uses data from another class more than its own | Move Method |
| Shotgun Surgery | One change requires edits in many classes | Move Method/Field, consolidate |
| Divergent Change | Class changes for multiple unrelated reasons | Extract Class |
| Duplicate Code | Same logic in multiple places | Extract Method/Function |
| Magic Numbers | Unexplained literals in code | Replace with Named Constant |
| Switch/Match on Type | Repeated `instanceof` or type checks | Replace with Polymorphism |

### Smell Examples

```typescript
// BAD — Primitive Obsession: money is a raw number, email is a raw string
function chargeUser(userId: string, amount: number, email: string) { /* ... */ }

// GOOD — Value Objects carry their own validation and behaviour
class Money {
  constructor(readonly cents: number, readonly currency: 'USD' | 'EUR') {
    if (cents < 0) throw new Error('Money cannot be negative');
  }
}
class Email {
  constructor(readonly value: string) {
    if (!value.includes('@')) throw new Error('Invalid email');
  }
}
function chargeUser(userId: string, amount: Money, email: Email) { /* ... */ }
```

```typescript
// BAD — Magic Numbers
if (user.age >= 65) applyDiscount(price * 0.25);

// GOOD — Named Constants
const SENIOR_AGE_THRESHOLD = 65;
const SENIOR_DISCOUNT_RATE = 0.25;
if (user.age >= SENIOR_AGE_THRESHOLD) applyDiscount(price * SENIOR_DISCOUNT_RATE);
```

---

## Language-Specific Idioms

### Python

```python
# Dataclass instead of verbose __init__
from dataclasses import dataclass, field

@dataclass
class Order:
    id: str
    items: list[str] = field(default_factory=list)
    total: float = 0.0

# Context manager for resource management
with open('file.txt') as f:
    data = f.read()  # file auto-closed, even on exception

# Generator for memory-efficient processing
def process_large_file(path: str):
    with open(path) as f:
        for line in f:           # reads line-by-line, not all into memory
            yield parse(line)

# Walrus operator for readability
if (match := pattern.search(text)) is not None:
    print(match.group(0))

# BAD — unpacking ignored with throwaway names
result = get_user_and_role()
user = result[0]
role = result[1]

# GOOD — structured unpacking
user, role = get_user_and_role()
```

### TypeScript

```typescript
// Discriminated union — exhaustive type narrowing
type Result<T> =
  | { success: true; data: T }
  | { success: false; error: string };

function handleResult<T>(result: Result<T>) {
  if (result.success) {
    console.log(result.data);    // TypeScript knows this is T
  } else {
    console.error(result.error); // TypeScript knows this is string
  }
}

// satisfies — validate type without widening
const config = {
  host: 'localhost',
  port: 5432,
} satisfies Record<string, string | number>;
// config.host is still `string` (not widened to `string | number`)

// Utility types
type PartialUser         = Partial<User>;                  // all fields optional
type ReadonlyUser        = Readonly<User>;                  // all fields readonly
type UserPreview         = Pick<User, 'id' | 'name'>;       // subset of fields
type UserWithoutPassword = Omit<User, 'password'>;          // exclude field

// BAD — casting away the type
const user = response.data as any;

// GOOD — parse and validate at the boundary
import { z } from 'zod';
const UserSchema = z.object({ id: z.string(), name: z.string() });
const user = UserSchema.parse(response.data);
```

### Go

```go
// Functional options pattern — flexible, forward-compatible constructors
type Server struct {
    host    string
    port    int
    timeout time.Duration
}

type Option func(*Server)

func WithTimeout(d time.Duration) Option {
    return func(s *Server) { s.timeout = d }
}

func NewServer(host string, port int, opts ...Option) *Server {
    s := &Server{host: host, port: port, timeout: 30 * time.Second}
    for _, opt := range opts {
        opt(s)
    }
    return s
}

// Usage
srv := NewServer("localhost", 8080, WithTimeout(5*time.Second))

// Error wrapping — preserve context, enable errors.Is / errors.As
if err := db.Query(); err != nil {
    return fmt.Errorf("fetching user %s: %w", userID, err)
}

// Table-driven tests — idiomatic Go
func TestAdd(t *testing.T) {
    cases := []struct{ a, b, want int }{
        {1, 2, 3},
        {0, 0, 0},
        {-1, 1, 0},
    }
    for _, tc := range cases {
        t.Run(fmt.Sprintf("%d+%d", tc.a, tc.b), func(t *testing.T) {
            got := Add(tc.a, tc.b)
            if got != tc.want {
                t.Errorf("got %d, want %d", got, tc.want)
            }
        })
    }
}
```

---

## Checklist

- [ ] Naming follows language convention (`snake_case` / `camelCase` / `PascalCase` per language)
- [ ] Functions have verb-phrase names; booleans use `is_` / `has_` / `can_` prefix
- [ ] Each function has a single, clear responsibility (< 30 lines as a guide)
- [ ] No magic numbers — named constants used for all literal values
- [ ] Dependencies injected (not instantiated inside the class)
- [ ] Design pattern applied only where it genuinely simplifies the code
- [ ] Code smells reviewed: no God Classes, Primitive Obsession, or Data Clumps
- [ ] Language-specific idioms used (dataclasses, discriminated unions, functional options)
- [ ] No duplicate logic — extracted into shared function or module
- [ ] PR reviewer can understand code intent without asking the author
