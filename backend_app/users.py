import uuid
from typing import Optional, Any
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, models
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy
)
from fastapi_users.db import SQLAlchemyUserDatabase
from backend_app.db import User, get_user_db
from passlib.context import CryptContext
from fastapi_users.password import PasswordHelper

SECRET = "sakjdhkjad872323"



# 2. 包装成 FastAPI Users 需要的 PasswordHelper
# 注意：这里导入的是 fastapi_users.password.PasswordHelper
# 它本质上就是对 pwd_context 的一个封装

class UserManager(BaseUserManager[User, str]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    # --- 必须添加这个方法来解决 NotImplementedError ---
    def parse_id(self, value: Any) -> str:
        """
        将 JWT Token 中的 sub (user_id) 转换为程序可以处理的类型。
        因为我们要兼容多种格式，统一返回字符串。
        """
        if value is None:
            return None
        return str(value)



    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(self, user: User, token: str, request: Optional[Request] = None):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(self, user: User, token: str, request: Optional[Request] = None):
        print(f"Verification requested for user {user.id}. Verification token: {token}")


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

def get_jwt_strategy():
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, str](get_user_manager, [auth_backend])
current_active_user = fastapi_users.current_user(active=True)