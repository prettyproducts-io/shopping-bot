import secrets

# Generate a secure, random JWT secret key
secure_key = secrets.token_hex(32)
print(f'JWT_SECRET_KEY: {secure_key}')