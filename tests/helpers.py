import json


class FakeHttpResponse:
    def __init__(self, status_code=200, content=b"", json_data=None, headers=None, reason="OK"):
        self.status_code = status_code
        self.content = content if isinstance(content, bytes) else content.encode()
        self.reason = reason
        self.headers = headers or {}
        self._json_data = json_data
        self.text = self.content.decode() if self.content else ""

    def json(self):
        if self._json_data is not None:
            return self._json_data
        return json.loads(self.content.decode())
