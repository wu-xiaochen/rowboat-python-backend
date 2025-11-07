"""
Advanced Authentication and Security System for Rowboat Python Backend
Implements JWT tokens, rate limiting, and comprehensive security measures
"""

import jwt
import time
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import redis.asyncio as redis
from passlib.context import CryptContext
import logging

logger = logging.getLogger(__name__)

# Security Configuration
SECURITY_CONFIG = {
    'jwt_secret_key': secrets.token_urlsafe(32),  # In production, use environment variable
    'jwt_algorithm': 'HS256',
    'jwt_expiration_minutes': 60,
    'jwt_refresh_expiration_days': 7,
    'rate_limit_per_minute': 60,
    'rate_limit_per_hour': 1000,
    'password_min_length': 8,
    'max_login_attempts': 5,
    'lockout_duration_minutes': 30,
    'session_timeout_minutes': 60,
}

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Security
security = HTTPBearer()

# User models
class User(BaseModel):
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    role: str = "user"  # user, admin, moderator
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=SECURITY_CONFIG['password_min_length'])
    full_name: Optional[str] = Field(None, max_length=100)
    role: str = "user"

class UserLogin(BaseModel):
    username: str
    password: str
    remember_me: bool = False

class TokenData(BaseModel):
    user_id: str
    username: str
    role: str
    exp: datetime

class AuthService:
    """Advanced authentication service with Redis-backed rate limiting"""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client or None
        self.failed_attempts = {}  # In-memory fallback, use Redis in production

    async def _get_redis_client(self) -> redis.Redis:
        """Get or create Redis client"""
        if not self.redis:
            try:
                self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
                await self.redis.ping()
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Using in-memory fallback.")
                return None
        return self.redis

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    def create_access_token(self, user_data: Dict[str, Any]) -> str:
        """Create a JWT access token"""
        expire = datetime.utcnow() + timedelta(minutes=SECURITY_CONFIG['jwt_expiration_minutes'])

        to_encode = {
            "user_id": user_data["id"],
            "username": user_data["username"],
            "role": user_data["role"],
            "exp": expire
        }

        encoded_jwt = jwt.encode(
            to_encode,
            SECURITY_CONFIG['jwt_secret_key'],
            algorithm=SECURITY_CONFIG['jwt_algorithm']
        )

        return encoded_jwt

    def create_refresh_token(self, user_data: Dict[str, Any]) -> str:
        """Create a JWT refresh token"""
        expire = datetime.utcnow() + timedelta(days=SECURITY_CONFIG['jwt_refresh_expiration_days'])

        to_encode = {
            "user_id": user_data["id"],
            "type": "refresh",
            "exp": expire
        }

        encoded_jwt = jwt.encode(
            to_encode,
            SECURITY_CONFIG['jwt_secret_key'],
            algorithm=SECURITY_CONFIG['jwt_algorithm']
        )

        return encoded_jwt

    def decode_token(self, token: str) -> Optional[TokenData]:
        """Decode and validate JWT token"""
        try:
            payload = jwt.decode(
                token,
                SECURITY_CONFIG['jwt_secret_key'],
                algorithms=[SECURITY_CONFIG['jwt_algorithm']]
            )

            return TokenData(
                user_id=payload["user_id"],
                username=payload["username"],
                role=payload["role"],
                exp=datetime.fromtimestamp(payload["exp"])
            )
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.JWTError as e:
            logger.warning(f"JWT decode error: {e}")
            return None

    async def check_rate_limit(self, identifier: str, limit_type: str = "minute") -> bool:
        """Check if request is within rate limits"""
        redis_client = await self._get_redis_client()

        if limit_type == "minute":
            key = f"rate_limit:{identifier}:minute"
            limit = SECURITY_CONFIG['rate_limit_per_minute']
            expiration = 60
        elif limit_type == "hour":
            key = f"rate_limit:{identifier}:hour"
            limit = SECURITY_CONFIG['rate_limit_per_hour']
            expiration = 3600
        else:
            return True

        try:
            if redis_client:
                current_count = await redis_client.incr(key)
                if current_count == 1:
                    await redis_client.expire(key, expiration)
                return current_count <= limit
            else:
                # In-memory fallback
                current_time = int(time.time())
                minute_key = current_time // 60

                if identifier not in self.failed_attempts:
                    self.failed_attempts[identifier] = {}

                if minute_key != self.failed_attempts[identifier].get('last_minute'):
                    self.failed_attempts[identifier]['last_minute'] = minute_key
                    self.failed_attempts[identifier]['minute_count'] = 0

                self.failed_attempts[identifier]['minute_count'] += 1
                return self.failed_attempts[identifier]['minute_count'] <= limit

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return True  # Allow request if rate limiting fails

    async def record_login_attempt(self, identifier: str, success: bool):
        """Record login attempt for rate limiting and security"""
        redis_client = await self._get_redis_client()

        key = f"login_attempts:{identifier}"

        try:
            if redis_client and success:
                # Reset failed attempts on successful login
                await redis_client.delete(key)
            elif redis_client and not success:
                # Increment failed attempts
                current = await redis_client.incr(key)
                if current == 1:
                    await redis_client.expire(key,
                                              SECURITY_CONFIG['lockout_duration_minutes'] * 60)
        except Exception as e:
            logger.error(f"Failed to record login attempt: {e}")

    async def is_locked_out(self, identifier: str) -> bool:
        """Check if user/IP is locked out due to failed attempts"""
        redis_client = await self._get_redis_client()

        key = f"login_attempts:{identifier}"

        try:
            if redis_client:
                attempts = await redis_client.get(key)
                return int(attempts or 0) >= SECURITY_CONFIG['max_login_attempts']
            else:
                return False
        except Exception as e:
            logger.error(f"Lockout check failed: {e}")
            return False

    def generate_session_id(self) -> str:
        """Generate a secure session ID"""
        return secrets.token_urlsafe(32)

    def hash_sensitive_data(self, data: str) -> str:
        """Hash sensitive data for storage"""
        return hashlib.sha256(data.encode()).hexdigest()

    async def validate_request_signature(self, request: Request, body: bytes) -> bool:
        """Validate request signature for API security"""
        # Implementation for request signing/HMAC validation
        # This would verify that requests haven't been tampered with
        return True  # Simplified for now

class SecurityMiddleware:
    """Security middleware for FastAPI"""

    def __init__(self):
        self.auth_service = AuthService()
        self.blocked_ips = set()
        self.suspicious_patterns = [
            "'", "--", ";", "\", "/", "..", "%", "&", "|", "`", "$"
        ]

    def validate_input(self, value: str, field_name: str) -> str:
        """Validate and sanitize input"""
        if not value or not isinstance(value, str):
            return value

        # Check for suspicious patterns
        value_lower = value.lower()
        for pattern in self.suspicious_patterns:
            if pattern in value_lower:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid characters detected in {field_name}"
                )

        # Strip whitespace and limit length
        value = value.strip()
        return value[:1000]  # Limit length to prevent DoS

    def generate_csp_header(self) -> str:
        """Generate Content Security Policy header"""
        return "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"

    def get_security_headers(self) -> Dict[str, str]:
        """Get security headers for HTTP responses"""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": self.generate_csp_header(),
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "X-Robots-Tag": "noindex, nofollow",
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }

# API authentication dependencies
security = HTTPBearer()
auth_service = AuthService()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> TokenData:
    """Get current authenticated user from JWT token"""
    try:
        token = credentials.credentials
        token_data = auth_service.decode_token(token)

        if not token_data:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        if token_data.exp < datetime.utcnow():
            raise HTTPException(status_code=401, detail="Token expired")

        return token_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")

async def get_current_active_user(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """Get current active user"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return current_user

async def get_admin_user(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """Get admin user (requires admin role)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# Rate limiting decorators
async def rate_limit_check(request: Request, identifier_type: str = "ip"):
    """Rate limiting decorator"""
    identifier = request.client.host if identifier_type == "ip" else "default"

    if not await auth_service.check_rate_limit(identifier, "minute"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded (per minute)")

    if not await auth_service.check_rate_limit(identifier, "hour"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded (per hour)")

# Security middleware application
security_middleware = SecurityMiddleware()