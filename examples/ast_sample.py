class UserService:
    def get_user(self, user_id):
        return user_id

    async def deactivate_user(self, user_id):
        return user_id


def create_service():
    return UserService()
