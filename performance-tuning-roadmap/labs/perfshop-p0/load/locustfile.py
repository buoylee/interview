from locust import HttpUser, between, task


class ProductUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(4)
    def product_detail(self):
        self.client.get("/api/products/1")

    @task(1)
    def product_search(self):
        self.client.get("/api/products/search?q=electronics")

