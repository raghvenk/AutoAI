# Password reset

## Requirements

- REQ-1: A user can request a password-reset link using a registered email address.
- REQ-2: The application always displays the same confirmation message, whether the email exists or not.
- REQ-3: A reset link expires after 30 minutes and can be used only once.
- REQ-4: The new password must contain at least 12 characters, one uppercase letter, one number, and one symbol.
- REQ-5: After a successful reset, all existing sessions are revoked.
