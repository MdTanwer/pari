"""PARI Layer 7: Output Handling and Context Hygiene.

Architectural Purpose:
    Closes the #1 failure mode in the Failure Mode Atlas: Unbounded stdout poisoning.
    Prevents large tool outputs (e.g. cat massive.log, npm install, pytest) from flooding
    the model's context window and displacing core instructions.

Subsystems:
    - spooler: 50KB / 2k-line disk spooler storing raw outputs in sidecar files
    - truncation: Head/tail extraction preserving stack traces and return headers
    - parser: Structured test failure extractors (pytest, jest, cargo)
"""

# Placeholder imports will be exported once implementations are added
