"""
Soul Engine — Ollama Proxy Server
Intercepts Ollama API calls and applies Soul Engine architecture before forwarding.
Hindsight (or any tool) calls this proxy instead of Ollama directly.
"""

import json
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError
import threading

# Add Soul Engine to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from soul_engine.wrappers.ollama_soul_adapter import OllamaSoulAdapter


class OllamaSoulProxyHandler(BaseHTTPRequestHandler):
    """
    HTTP proxy that wraps Ollama API with Soul Engine.
    
    Routes:
    - POST /api/generate → Soul Engine + Ollama
    - POST /api/chat → Soul Engine + Ollama
    - GET /api/tags → Pass through to Ollama
    - GET /health → Proxy health check
    """
    
    OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    DEFAULT_MODEL = os.environ.get("SOUL_ENGINE_MODEL", "llama3.2:3b")
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass
    
    def _send_json(self, status: int, data: dict):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_GET(self):
        """Handle GET requests — pass through to Ollama."""
        if self.path == "/health":
            self._send_json(200, {
                "status": "healthy",
                "soul_engine": "enabled",
                "model": self.DEFAULT_MODEL
            })
            return
        
        # Pass through to Ollama
        try:
            req = Request(f"{self.OLLAMA_URL}{self.path}", method="GET")
            with urlopen(req, timeout=10) as resp:
                self.send_response(resp.status)
                for header, value in resp.headers.items():
                    self.send_header(header, value)
                self.end_headers()
                self.wfile.write(resp.read())
        except URLError as e:
            self._send_json(502, {"error": f"Ollama unreachable: {str(e)}"})
    
    def do_POST(self):
        """Handle POST requests — intercept generate/chat."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()
        
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON"})
            return
        
        # Only intercept generate and chat endpoints
        if self.path not in ["/api/generate", "/api/chat"]:
            # Pass through to Ollama
            self._proxy_to_ollama(body)
            return
        
        # Extract user prompt from payload
        user_prompt = self._extract_prompt(payload)
        model = payload.get("model", self.DEFAULT_MODEL)
        
        # Run through Soul Engine
        adapter = OllamaSoulAdapter(model=model)
        result = adapter.generate(user_prompt)
        
        # Build Ollama-compatible response
        ollama_response = {
            "model": model,
            "created_at": "2026-07-25T00:00:00Z",
            "response": result.output,
            "done": True,
            "done_reason": "stop",
            "context": [],
            "total_duration": 0,
            "load_duration": 0,
            "prompt_eval_count": 0,
            "prompt_eval_duration": 0,
            "eval_count": 0,
            "eval_duration": 0,
            # Soul Engine metadata (non-standard, for debugging)
            "_soul_engine": {
                "quality_score": result.quality_score,
                "gates_passed": result.gates_passed,
                "gates_failed": result.gates_failed,
                "reasoning_trace": result.reasoning_trace,
                "claim_provenance": result.claim_provenance
            }
        }
        
        self._send_json(200, ollama_response)
    
    def _extract_prompt(self, payload: dict) -> str:
        """Extract the user prompt from Ollama payload."""
        if "prompt" in payload:
            return payload["prompt"]
        elif "messages" in payload:
            # Chat format — extract last user message
            messages = payload["messages"]
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    return msg.get("content", "")
            return ""
        return ""
    
    def _proxy_to_ollama(self, body: str):
        """Pass request through to Ollama."""
        try:
            req = Request(
                f"{self.OLLAMA_URL}{self.path}",
                data=body.encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urlopen(req, timeout=60) as resp:
                self.send_response(resp.status)
                for header, value in resp.headers.items():
                    self.send_header(header, value)
                self.end_headers()
                self.wfile.write(resp.read())
        except URLError as e:
            self._send_json(502, {"error": f"Ollama unreachable: {str(e)}"})


def run_proxy_server(port: int = 11435):
    """Run the Soul Engine Ollama proxy server."""
    server = HTTPServer(("0.0.0.0", port), OllamaSoulProxyHandler)
    print(f"Soul Engine Ollama Proxy running on port {port}")
    print(f"Forwarding to: {OllamaSoulProxyHandler.OLLAMA_URL}")
    print(f"Default model: {OllamaSoulProxyHandler.DEFAULT_MODEL}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down proxy...")
        server.shutdown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Soul Engine Ollama Proxy")
    parser.add_argument("--port", type=int, default=11435, help="Proxy port (default: 11435)")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama base URL")
    args = parser.parse_args()
    
    OllamaSoulProxyHandler.OLLAMA_URL = args.ollama_url
    run_proxy_server(args.port)
