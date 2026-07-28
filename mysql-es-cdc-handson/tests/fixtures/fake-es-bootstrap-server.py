#!/usr/bin/env python3
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

mode, port_file, log_file = sys.argv[1:]

properties = json.loads(Path("infra/elasticsearch/index-template.json").read_text())["template"]["mappings"]
compatible_mapping = {
    "products_v2": {
        "mappings": {
            **properties,
            "_meta": {
                "schema_version": 1,
                "deletion_mode": "tombstone",
                "generation": "products_v2",
            },
        }
    }
}


def normalized_template():
    template = {
        "settings": {
            "index": {
                "number_of_shards": "1",
                "number_of_replicas": "0",
            }
        },
        "mappings": properties,
    }
    index_template = {
        "index_patterns": ["products_v*", "products_adapter_v*"],
        "template": template,
        "composed_of": [],
    }
    if mode == "malicious-composed-of":
        index_template["composed_of"] = ["malicious-component"]
    elif mode == "unexpected-data-stream":
        index_template["data_stream"] = {}
    elif mode == "extra-template-setting":
        template["settings"]["index"]["refresh_interval"] = "1s"
    elif mode == "extra-template-alias":
        template["aliases"] = {"unexpected_alias": {}}
    return {"index_templates": [{"name": "products-search", "index_template": index_template}]}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def respond(self, status, body=None):
        payload = json.dumps(body or {}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def record(self):
        with open(log_file, "a", encoding="utf-8") as stream:
            stream.write(f"{self.command} {self.path}\n")

    def do_HEAD(self):
        self.record()
        self.respond(200 if self.path == "/products_v2" else 404)

    def do_GET(self):
        self.record()
        if self.path == "/_index_template/products-search":
            if mode == "incompatible-template":
                self.respond(200, {"index_templates": [{"index_template": {"index_patterns": ["wrong-*"], "template": {}}}]})
            elif mode in {"malicious-composed-of", "unexpected-data-stream", "extra-template-setting", "extra-template-alias"}:
                self.respond(200, normalized_template())
            else:
                self.respond(404)
        elif self.path == "/products_v2/_mapping":
            if mode == "incompatible-index":
                self.respond(200, {"products_v2": {"mappings": {"_meta": {"schema_version": 999}}}})
            else:
                self.respond(200, compatible_mapping)
        elif self.path == "/_alias/products_write" and mode == "incompatible-alias":
            self.respond(200, {"other_index": {"aliases": {"products_write": {"is_write_index": True}}}})
        elif self.path.startswith("/_alias/"):
            self.respond(404)
        else:
            self.respond(404)

    def do_PUT(self):
        self.record()
        self.respond(200, {"acknowledged": True})

    def do_POST(self):
        self.record()
        self.respond(200, {"acknowledged": True})


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
Path(port_file).write_text(str(server.server_port))
server.serve_forever()
