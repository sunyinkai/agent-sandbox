class UserService:
    @hello("123")
    @world("234")
    @router.get("/users")
    def get_user(self, user_id):
        async def inner():
            return user_id

    @router.deactive("/users")
    async def deactivate_user(self, user_id):
        async def inner():
            return user_id
