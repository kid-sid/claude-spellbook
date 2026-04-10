Generate a changelog from git history since the last release tag.

## Instructions

1. Find the last release tag:
   ```
   git describe --tags --abbrev=0
   ```
   If no tags exist, use the first commit: `git rev-list --max-parents=0 HEAD`

2. Get all commits since that tag:
   ```
   git log <last-tag>..HEAD --pretty=format:"%H %s" --no-merges
   ```

3. If a specific version argument was provided by the user (e.g. `v1.3.0`), use that as the new version. Otherwise, infer the next version by incrementing the last tag:
   - Any `feat:` commit → bump minor (e.g. v1.2.0 → v1.3.0)
   - Only `fix:` / `chore:` / `docs:` → bump patch (e.g. v1.2.0 → v1.2.1)
   - Breaking change (`feat!:` or `BREAKING CHANGE:` in body) → bump major

4. Group commits by conventional commit type:

   | Prefix | Changelog section |
   |---|---|
   | `feat:` / `feat!:` | Added |
   | `fix:` | Fixed |
   | `docs:` | Documentation |
   | `refactor:` | Changed |
   | `perf:` | Performance |
   | `chore:` / `ci:` / `build:` | Maintenance |
   | `revert:` | Reverted |

   Discard commits without a conventional prefix (unless they're meaningful — use judgment).

5. For each commit, strip the type prefix and capitalise the first letter. Include the short SHA as a link reference if on GitHub (use `git remote get-url origin` to determine the base URL).

6. Output the changelog block in [Keep a Changelog](https://keepachangelog.com) format:

```markdown
## [<version>] - <YYYY-MM-DD>

### Added
- Short description of feature (#sha)

### Fixed
- Short description of fix (#sha)

### Changed
- Short description of refactor (#sha)

### Maintenance
- Short description of chore (#sha)
```

7. If `CHANGELOG.md` exists in the repo root, prepend the new block after the `# Changelog` header (or at the top if no header). Show the user the final result and ask whether to write it to the file.

8. If `CHANGELOG.md` does not exist, output the block only — do not create the file unless the user asks.

## Notes

- Omit sections with no entries.
- If the commit range is empty (no commits since last tag), say so and stop.
- Do not include merge commits.
- Breaking changes get a `> ⚠ Breaking change:` callout under the relevant entry.
