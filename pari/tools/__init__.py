"""PARI Standard Tool System.

Bridges model tool definitions to sandbox-contained, concurrency-safe execution layers.

Available Tools:
    - bash: Execute shell commands inside the Layer 0 sandbox with output spooling
    - read_file: Safe workspace-relative file reading
    - edit_file: Atomic, Stop-on-Ambiguity search and replace
    - write_file: Atomic file creation / overwrite
    - find_files: Workspace file globbing respecting ignore boundaries
    - grep_search: Substring and regex text search across repository files
"""

# Placeholder imports will be exported once implementations are added
