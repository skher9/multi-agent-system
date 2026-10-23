"""Print the API's OpenAPI spec as JSON, without starting a server.

Used by the web app's type generator: pnpm --filter web gen:api
"""

import json

from api.main import app

if __name__ == "__main__":
    print(json.dumps(app.openapi(), indent=2))
