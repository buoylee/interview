def fetch_profile(client, user_id):
    return client.get(user_id)
