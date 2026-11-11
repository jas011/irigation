import asyncio
import time
import unittest

import httpx

from app.services.bhoonidhi.bhoonidhi_client import BhoonidhiAuthError, BhoonidhiClient, _geometry_bbox


class BhoonidhiClientTests(unittest.IsolatedAsyncioTestCase):
    def make_client(self, handler):
        transport = httpx.MockTransport(handler)
        return BhoonidhiClient(
            base_url="https://test.bhoonidhi",
            user_id="user",
            password="password",
            client_factory=lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs),
        )

    async def test_password_auth_parses_and_caches_token(self):
        calls = []
        async def handler(request):
            calls.append(request)
            return httpx.Response(200, json={"userId": "user", "access_token": "a", "refresh_token": "r", "token_type": "Bearer", "expires_in": 1200})
        client = self.make_client(handler)
        first = await client._authenticate()
        second = await client._authenticate()
        self.assertEqual(first.access_token, "a")
        self.assertIs(first, second)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].url.path, "/auth/token")
        self.assertEqual(calls[0].read(), b'{"userId":"user","password":"password","grant_type":"password"}')

    async def test_missing_credentials(self):
        client = BhoonidhiClient(base_url="https://test", user_id="", password="")
        with self.assertRaises(BhoonidhiAuthError):
            await client._authenticate()

    async def test_refresh_and_401_retry(self):
        calls = []
        async def handler(request):
            calls.append((request.method, request.url.path))
            if request.url.path == "/auth/token":
                if len([x for x in calls if x[1] == "/auth/token"]) == 1:
                    return httpx.Response(200, json={"userId": "user", "access_token": "a", "refresh_token": "r", "expires_in": 0})
                return httpx.Response(200, json={"userId": "user", "access_token": "b", "refresh_token": "r2", "expires_in": 1200})
            if len([x for x in calls if x[1] == "/data/collections"]) == 1:
                return httpx.Response(401, json={"message": "expired"})
            return httpx.Response(200, json={"collections": []})
        client = self.make_client(handler)
        client.token_margin = 0
        result = await client.get_collections()
        self.assertEqual(result, {"collections": []})
        self.assertEqual([x[1] for x in calls], ["/auth/token", "/data/collections", "/auth/token", "/data/collections"])

    async def test_pagination_and_deduplication(self):
        async def handler(request):
            if request.url.path == "/auth/token":
                return httpx.Response(200, json={"access_token": "a", "expires_in": 1200})
            if request.url.path == "/data/search":
                return httpx.Response(200, json={"type": "FeatureCollection", "features": [{"id": "one"}], "links": [{"rel": "next", "href": "https://test.bhoonidhi/page2"}]})
            return httpx.Response(200, json={"type": "FeatureCollection", "features": [{"id": "one"}, {"id": "two"}], "links": []})
        result = await self.make_client(handler).search({"collections": ["x"], "bbox": [1, 2, 3, 4]})
        self.assertEqual([item["id"] for item in result["features"]], ["one", "two"])

    async def test_empty_search_is_not_auth_failure(self):
        async def handler(request):
            if request.url.path == "/auth/token":
                return httpx.Response(200, json={"access_token": "a", "expires_in": 1200})
            return httpx.Response(200, json={"type": "FeatureCollection", "context": {"returned": 0}, "features": []})
        result = await self.make_client(handler).search({"collections": ["x"]})
        self.assertEqual(result["features"], [])

    async def test_no_results_404_is_an_empty_catalogue_response(self):
        async def handler(request):
            if request.url.path == "/auth/token":
                return httpx.Response(200, json={"access_token": "a", "expires_in": 1200})
            return httpx.Response(404, json={"Description": "NO RESULTS FOUND"})
        result = await self.make_client(handler).search({"collections": ["x"]})
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertEqual(result["features"], [])

    def test_geometry_bbox_accepts_shapely_style_coordinate_tuples(self):
        geometry = {
            "type": "Polygon",
            "coordinates": ((77.1, 28.5), (77.4, 28.5), (77.4, 28.8), (77.1, 28.5)),
        }
        self.assertEqual(_geometry_bbox(geometry), [77.1, 28.5, 77.4, 28.8])


if __name__ == "__main__":
    unittest.main()
