import hashlib
import hmac
import secrets
from datetime import datetime,timedelta


def hash_password(password,salt=None):
 salt=salt or secrets.token_hex(16)
 digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),210_000).hex()
 return f'pbkdf2_sha256${salt}${digest}'


def verify_password(password,encoded):
 try:
  algorithm,salt,expected=encoded.split('$',2)
  if algorithm!='pbkdf2_sha256': return False
  actual=hash_password(password,salt).split('$',2)[2]
  return hmac.compare_digest(actual,expected)
 except (ValueError,TypeError):
  return False


def new_token(): return secrets.token_urlsafe(32)
def token_hash(token): return hashlib.sha256(token.encode()).hexdigest()
def token_expiry(hours=12): return datetime.utcnow()+timedelta(hours=hours)
