# Planted bugs (answer key, keep this out of the LLM's context)

| # | Requirement | Bug | Test that should catch it |
|---|-------------|-----|---------------------------|
| 1 | Rate limiting (5/hour) | Not enforced; 6th request returns 200 | 6× reset request → expect 429 |
| 2 | No user enumeration | Unknown email returns 404 "No account with that email" | unknown email → expect 200 + generic message |
| 3 | Token expiry (15 min) | Expiry never checked | expired token → expect 400 "Token expired" |
| 4 | Single-use token | Token never invalidated | confirm twice → expect 400 |
| 5 | Password ≥ 8 chars | Accepts ≥ 6 | 7-char password → expect 422 |
| 6 | UI (enumeration) | Forgot-password page shows raw server error | UI flow with unknown email |

With the mock LLM, the sample run should show 5 failing tests (bugs 1-5) and 8 passing ones.
Fix a bug live during the pitch and hit "Re-run" to show the suite go green.
