Explain a code file, function, or architectural pattern in detail with context.

## Instructions

1. Read the target that the user specifies:
   - A specific file path
   - A function or class name (search for it in the codebase)
   - A directory (explain the module/package architecture)
   - If nothing specified, use the most recently edited file

2. Determine the appropriate level of explanation:
   - **File-level**: overall purpose, key exports, dependencies, how it fits in the system
   - **Function-level**: inputs, outputs, algorithm, edge cases, side effects
   - **Architecture-level**: component relationships, data flow, design patterns used
   - **Line-level**: what specific complex lines do (only for genuinely tricky code)

3. Structure the explanation:

### For a File
```
## {filename}

### Purpose
{One paragraph: what this file does and why it exists}

### Key Components
- `{export/class/function}` — {what it does}
- `{export/class/function}` — {what it does}

### Dependencies
- **Imports from:** {list of modules this file depends on}
- **Used by:** {list of files that import from this file}

### Data Flow
{How data enters, is transformed, and exits this file}

### Design Decisions
- {Why was it structured this way?}
- {What patterns are used? (factory, observer, middleware, etc.)}

### Gotchas
- {Non-obvious behavior or edge cases}
- {Things that might surprise a new reader}
```

### For a Function
```
## `{functionName}()`

### Signature
{full function signature with types}

### Purpose
{What does this function do? One paragraph.}

### Parameters
- `{param}` ({type}): {description, constraints, defaults}

### Returns
- ({type}): {description of return value}

### Algorithm
1. {Step 1}
2. {Step 2}
3. {Step 3}

### Edge Cases
- {What happens with null/empty input?}
- {What happens at boundary values?}
- {What errors can it throw?}

### Example Usage
```{lang}
{realistic usage example}
```

### Side Effects
- {Database writes, HTTP calls, file I/O, global state mutations}

### Performance
- **Time complexity:** O({n})
- **Space complexity:** O({n})
- {Any known performance considerations}
```

### For Architecture
```
## {Module/System Name} Architecture

### Overview
{High-level description of what this system does}

### Components
{List each component and its responsibility}

### Data Flow
{How requests/data flow through the system}
1. {Entry point}
2. {Processing step}
3. {Storage/output}

### Key Patterns
- {Pattern 1}: {where and why it's used}
- {Pattern 2}: {where and why it's used}

### External Dependencies
- {Service/API}: {what it's used for}

### Configuration
- {Key config values and what they control}
```

4. Adapt to the reader:
   - If the code is in a language/framework the reader might not know well, explain idioms
   - If there are design patterns, name them and explain why they were chosen
   - If there's complex logic, walk through it step by step with examples
   - If there are references to domain concepts, explain them

5. Always ground explanations in the actual code — quote specific lines when helpful.

## Output
- Structured explanation at the appropriate level of detail
- Cross-references to related files and components
- Practical context: why it exists, how to modify it, what to watch out for
