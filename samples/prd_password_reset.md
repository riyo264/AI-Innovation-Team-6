# PRD: Login & Password Reset

## Overview
Users sign in with email and password. Users who forget their password can request a
reset link by email and set a new password using a single-use token.

## Endpoints
- `POST /api/login` — body `{email, password}`
- `POST /api/password-reset/request` — body `{email}`
- `POST /api/password-reset/confirm` — body `{token, new_password}`
- UI pages: `/login`, `/forgot-password`, `/reset-password`

## Requirements

1. **Login.** A registered user who submits the correct email and password receives HTTP 200
   and a session token. Wrong credentials return HTTP 401 with the message
   "Invalid credentials". The message must not reveal whether the email exists.

2. **Reset request.** Submitting an email to the reset-request endpoint always returns
   HTTP 200 with the message "If an account exists, a reset link has been sent",
   whether or not the email is registered (no user enumeration).

3. **Rate limiting.** A single email may request at most 5 resets per hour. The 6th
   request within the hour returns HTTP 429.

4. **Token expiry.** Reset tokens expire 15 minutes after issue. Confirming with an
   expired token returns HTTP 400 with "Token expired".

5. **Single use.** A reset token can be used once. Re-using a token returns HTTP 400.

6. **Password policy.** New passwords must be at least 8 characters. Shorter passwords
   return HTTP 422.

7. **UI feedback.** The forgot-password page shows a confirmation message after submit.
   Reset emails should be sent promptly.
