def fetch_profile(client, user_id):
    for _ in range(3):
        try:
            return client.get(user_id)
        except TimeoutError:
            pass
    return {}
