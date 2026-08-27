import sys
import os
import importlib
from dotenv import load_dotenv
from fastmcp import FastMCP

# Load environment variables from project root .env file
# This allows keeping credentials out of docker-compose.yml
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, ".env"))

# Setup system path to resolve imports in docker environment
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Add /app to sys.path if not present (usually set by PYTHONPATH=/app)
app_dir = os.path.dirname(current_dir)
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Add datadog_monitoring_v2 src to sys.path to allow standalone local running
v2_src = os.path.join(app_dir, "crews", "datadog_monitoring_v2", "src")
if os.path.exists(v2_src) and v2_src not in sys.path:
    sys.path.insert(0, v2_src)

# Initialize FastMCP server
mcp = FastMCP("Shared DevOps Monitoring MCP Server")

def load_modules():
    modules_dir = os.path.join(current_dir, "modules")
    if not os.path.exists(modules_dir):
        print(f"Modules directory not found at: {modules_dir}", file=sys.stderr)
        return
        
    for filename in os.listdir(modules_dir):
        if filename.endswith(".py") and filename != "__init__.py":
            module_name = filename[:-3]
            try:
                # Dynamic import from modules package
                module = importlib.import_module(f"modules.{module_name}")
                if hasattr(module, "register"):
                    module.register(mcp)
                    print(f"Loaded and registered module: {module_name}")
            except Exception as e:
                print(f"Error loading module '{module_name}': {e}", file=sys.stderr)

# Load all service modules
load_modules()

if __name__ == "__main__":
    # Start the server using SSE transport on port 8012
    # Bind to 0.0.0.0 to be accessible across the network/Docker containers
    port = int(os.environ.get("FASTMCP_PORT", 8012))
    host = os.environ.get("FASTMCP_HOST", "0.0.0.0")
    print(f"Starting Shared MCP Server via SSE on {host}:{port}...", flush=True)
    mcp.run(transport="sse", host=host, port=port)
