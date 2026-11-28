# Security Policy — UE5 Build, Crash-Log & VRAM Doctor

## Supported Versions

| Version | Supported |
| :--- | :---: |
| `1.0.x` | Yes |
| `< 1.0.x` | No |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for suspected security vulnerabilities, sanitizer bypasses, or path/command injection findings.

Report security issues privately by email to:

- **Security Contact:** `argoness@veristrux.com`
- **Subject Line:** `[SECURITY] ue5-doctor: <brief summary>`

Include a minimal reproducible input or command, affected version/commit SHA, and expected vs. observed behavior. You can expect an initial acknowledgment within **48 hours** and coordinated disclosure once a verified fix and regression test are released on `main`.

## Scope & Design Guarantees

`ue5-doctor` runs locally on the developer's machine using Python 3.10+ standard library modules with zero runtime third-party packages and zero content telemetry.
