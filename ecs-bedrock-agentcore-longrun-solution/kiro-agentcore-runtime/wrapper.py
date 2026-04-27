"""AgentCore wrapper: BedrockAgentCoreApp SDK + Kiro CLI ACP with async task management."""
import json, os, subprocess, threading, queue, logging, urllib.request, re
from bedrock_agentcore.runtime import BedrockAgentCoreApp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def resolve_ssm_secrets():
    """Resolve env vars from SSM Parameter Store. Any env var ending in _SSM_PARAM
    will be fetched and set as the base name. e.g. KIRO_API_KEY_SSM_PARAM=/path/to/key
    sets KIRO_API_KEY to the parameter value."""
    import boto3
    ssm = boto3.client("ssm", region_name=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-west-2")))
    for k, v in list(os.environ.items()):
        if k.endswith("_SSM_PARAM") and v:
            target = k[:-10]  # strip _SSM_PARAM
            try:
                resp = ssm.get_parameter(Name=v, WithDecryption=True)
                os.environ[target] = resp["Parameter"]["Value"]
                logger.info(f"Resolved {target} from SSM {v}")
            except Exception as e:
                logger.warning(f"Failed to resolve {target} from SSM {v}: {e}")


resolve_ssm_secrets()

app = BedrockAgentCoreApp()

# Store completed results by task_id
results = {}

INTEGRATION_PROFILE = os.getenv("INTEGRATION_PROFILE", "/app/profiles/default.json")


def load_integration_profile():
    """Load integration profile and return list of MCP server configs."""
    path = INTEGRATION_PROFILE
    if not path:
        return []
    try:
        if path.startswith("s3://"):
            import boto3
            parts = path[5:].split("/", 1)
            obj = boto3.client("s3").get_object(Bucket=parts[0], Key=parts[1])
            profile = json.loads(obj["Body"].read())
        else:
            with open(path) as f:
                profile = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load profile {path}: {e}")
        return []

    mcp_servers = []
    for integ in profile.get("integrations", []):
        if not integ.get("enabled"):
            continue
        name = integ.get("name", "unknown")
        required = integ.get("required_env", [])
        missing = [v for v in required if not os.environ.get(v)]
        if missing:
            logger.warning(f"Skipping {name}: missing env vars {missing}")
            continue
        server = integ.get("mcp_server", {})
        # Resolve ${VAR} references in env
        resolved_env = {}
        for k, v in server.get("env", {}).items():
            resolved_env[k] = re.sub(r'\$\{(\w+)\}', lambda m: os.environ.get(m.group(1), ''), v)
        mcp_servers.append({
            "command": server.get("command", ""),
            "args": server.get("args", []),
            "env": resolved_env,
        })
        logger.info(f"Integration enabled: {name}")
    return mcp_servers


def fetch_credentials():
    """Fetch IAM credentials from container metadata."""
    if os.environ.get("AWS_ACCESS_KEY_ID"):
        c = {"AWS_ACCESS_KEY_ID": os.environ["AWS_ACCESS_KEY_ID"],
             "AWS_SECRET_ACCESS_KEY": os.environ["AWS_SECRET_ACCESS_KEY"]}
        if os.environ.get("AWS_SESSION_TOKEN"):
            c["AWS_SESSION_TOKEN"] = os.environ["AWS_SESSION_TOKEN"]
        return c
    for v in ["AWS_CONTAINER_CREDENTIALS_RELATIVE_URI", "AWS_CONTAINER_CREDENTIALS_FULL_URI"]:
        uri = os.environ.get(v)
        if not uri:
            continue
        try:
            url = f"http://169.254.170.2{uri}" if v.endswith("RELATIVE_URI") else uri
            h = {}
            tok = os.environ.get("AWS_CONTAINER_AUTHORIZATION_TOKEN")
            if tok:
                h["Authorization"] = tok
            d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=5).read())
            return {"AWS_ACCESS_KEY_ID": d["AccessKeyId"], "AWS_SECRET_ACCESS_KEY": d["SecretAccessKey"], "AWS_SESSION_TOKEN": d["Token"]}
        except Exception as e:
            logger.warning(f"Cred fetch failed ({v}): {e}")
    return {}


class KiroACP:
    """Manages a single kiro-cli ACP process."""
    def __init__(self):
        self.proc = self.session_id = None
        self.pending, self.chunks = {}, {}
        self.next_id = 0
        self.lock = threading.Lock()
        self.ready = False

    def start(self):
        creds = fetch_credentials()
        env = os.environ.copy()
        env.update(creds)
        self.creds = creds
        self.proc = subprocess.Popen(
            ["kiro-cli", "acp", "--trust-all-tools"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, env=env)
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._log_stderr, daemon=True).start()
        self._call("initialize", {"protocolVersion": 1, "clientCapabilities": {}, "clientInfo": {"name": "agentcore", "version": "0.1"}})
        mcp_servers = load_integration_profile()
        r = self._call("session/new", {"cwd": "/tmp", "mcpServers": mcp_servers})
        self.session_id = r.get("result", {}).get("sessionId", "")
        self.ready = True
        logger.info(f"ACP ready, session={self.session_id}, integrations={len(mcp_servers)}")

    def _log_stderr(self):
        for line in self.proc.stderr:
            logger.warning(f"ACP: {line.rstrip()}")

    def _read(self):
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("method") == "session/request_permission":
                rid = msg.get("id")
                if rid:
                    opts = msg.get("params", {}).get("options", [])
                    oid = next((o.get("optionId") for o in opts if o.get("kind") == "allow_always"), "allow_always")
                    self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"outcome": {"outcome": "selected", "optionId": oid}}}) + "\n")
                    self.proc.stdin.flush()
                continue
            p = msg.get("params", {})
            u = p.get("update", {})
            if u.get("sessionUpdate") == "agent_message_chunk":
                t = u.get("content", {}).get("text", "")
                if t:
                    for chunks in self.chunks.values():
                        chunks.append(t)
            mid = msg.get("id")
            if mid is not None and mid in self.pending:
                self.pending[mid].put(msg)

    def _call(self, method, params, timeout=120):
        with self.lock:
            self.next_id += 1
            rid = self.next_id
        q = queue.Queue()
        self.pending[rid] = q
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}) + "\n")
        self.proc.stdin.flush()
        try:
            return q.get(timeout=timeout)
        except queue.Empty:
            return {"error": {"message": "timeout"}}
        finally:
            self.pending.pop(rid, None)

    def prompt(self, text):
        if not self.ready or not self.session_id:
            return "(agent not ready)"
        with self.lock:
            self.next_id += 1
            rid = self.next_id
        q = queue.Queue()
        self.pending[rid] = q
        self.chunks[rid] = []
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "method": "session/prompt", "params": {
            "sessionId": self.session_id, "prompt": [{"type": "text", "text": text}]}}) + "\n")
        self.proc.stdin.flush()
        try:
            q.get(timeout=300)
        except queue.Empty:
            pass
        finally:
            self.pending.pop(rid, None)
        return "".join(self.chunks.pop(rid, [])) or "(no response)"


acp = KiroACP()


def init_acp():
    """Initialize ACP in background thread."""
    try:
        acp.start()
    except Exception as e:
        logger.error(f"ACP init failed: {e}")


@app.entrypoint
def main(payload):
    """Handle incoming requests. Returns immediately for long-running tasks."""
    user_input = payload.get("input", payload.get("prompt", ""))

    # Check for result polling
    check_task = payload.get("check_task")
    if check_task:
        if check_task in results:
            return {"status": "complete", "task_id": check_task, "response": results.pop(check_task)}
        return {"status": "processing", "task_id": check_task}

    if not acp.ready:
        return {"status": "initializing", "response": "Agent is starting up, please retry in a moment."}

    # Start async task
    task_id = app.add_async_task("kiro_prompt")

    def run():
        try:
            result = acp.prompt(user_input)
            results[task_id] = result
        except Exception as e:
            results[task_id] = f"Error: {e}"
        finally:
            app.complete_async_task(task_id)

    threading.Thread(target=run, daemon=True).start()
    return {"status": "accepted", "task_id": task_id, "response": f"Working on your request..."}


if __name__ == "__main__":
    logger.info("Starting AgentCore wrapper with async task management")
    threading.Thread(target=init_acp, daemon=True).start()
    app.run()
