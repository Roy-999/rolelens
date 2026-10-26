# Local verification — 26 October 2026

Checks completed against the actual local implementation:

| Check | Result |
| --- | --- |
| Backend suite on Windows / Python 3.12 | 21 passed |
| Same suite inside the Linux / Python 3.11 backend image | 21 passed |
| Frontend production build | Passed |
| Frontend dependency audit, including development dependencies | 0 reported vulnerabilities |
| Python and frontend format checks | Passed |
| Three-service Compose build and startup without credentials | Passed; all services healthy |
| Actual browser workflow using headless Edge | Passed |
| Mobile overflow and navigation at 390 × 844 | Passed |
| Data and edited seed record persist across backend restart | Passed |
| Repeated seed preserves existing records and edits | Passed |
| Explicit demo reset restores 12 candidates and four jobs | Passed |
| New Git index artifact/credential-pattern check | Passed |

The browser workflow exercises candidate extraction, human review, save/edit, a two-document batch, job extraction/save/edit, matching, location filtering, empty searches, and disabled Gmail. Screenshots are actual captures from the reset sample dataset, at 1440px desktop and 390px mobile widths.

Gemini is verified with a constructed SDK client and mocked success/error responses, including invalid JSON, image input, quota exhaustion, timeout, and invalid embeddings. **No live Gemini or Gmail account was used**, and Atlas search was not tested against an external cluster. Those optional integrations need the owner's credentials and quota.

CI configuration is included; no workflow has been dispatched to GitHub. Reported dependency findings reflect the local audit date and are not a permanent security guarantee. The backend test run emits third-party deprecation warnings; they do not fail the tests.
