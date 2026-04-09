Generate unit and integration tests for a given file or function.

## Instructions

1. Read the target file the user specifies (or the most recently edited file if none given).
2. Identify the language and detect the existing test framework:
   - Python: pytest (check for `conftest.py`, `pytest.ini`, `pyproject.toml`)
   - TypeScript: Jest or Vitest (check `package.json` for `jest` or `vitest`)
   - Go: stdlib `testing` package
   - Rust: stdlib `#[cfg(test)]` module
3. Identify all public functions/methods and their behavior:
   - What inputs do they accept?
   - What outputs do they produce?
   - What side effects do they have (DB, HTTP, file I/O)?
   - What error conditions exist?

4. Generate tests following the unit-testing skill patterns:
   - **AAA pattern** (Arrange / Act / Assert)
   - **Naming**: `test_<unit>_<scenario>_<expected>` (Python), `describe/it` (TS), `TestXxx` (Go)
   - **Edge cases**: null/None/nil, empty collections, boundary values
   - **Error paths**: invalid input, missing dependencies, timeout
   - **Parameterized tests** where multiple input/output pairs test the same logic

5. For functions with external dependencies (DB, HTTP, filesystem):
   - Generate integration test stubs using Testcontainers or test clients
   - Mock external I/O with appropriate library (unittest.mock, jest.fn(), interface-based in Go)

6. Place the test file in the correct location:
   - Python: `tests/test_<module>.py`
   - TypeScript: `<module>.test.ts` (co-located) or `__tests__/<module>.test.ts`
   - Go: `<module>_test.go` (same package)
   - Rust: `#[cfg(test)] mod tests` at bottom of same file, or `tests/` for integration

7. Run the tests to verify they pass. Fix any failures.

## Output
- The generated test file
- A summary of what was tested and what was deliberately excluded (with reasoning)
