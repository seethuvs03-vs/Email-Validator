# Email Validator

Check common ASCII email address syntax with Python 3 and no third-party dependencies.

```sh
python3 email_validator.py 'person+tag@example.com'
```

The command exits with status 0 for valid syntax and 1 for invalid syntax. It supports dot-separated local parts and DNS-style domain labels. Quoted local parts, domain literals, and Unicode addresses are outside its supported syntax. The check runs locally and cannot establish whether a mailbox exists or accepts mail.

Import `is_valid_email` from `email_validator` to use the check in Python code.
