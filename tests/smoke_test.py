import os
import subprocess
import time
import socket
import requests
import sys
from pathlib import Path

def find_free_port():
    s = socket.socket()
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def run_smoke_test():
    port = find_free_port()
    url = f"http://127.0.0.1:{port}"
    
    print(f"Starting FastAPI backend server on port {port}...")
    proc = subprocess.Popen(
        ["poetry", "run", "uvicorn", "src.api.main:app", "--port", str(port)],
        env={**os.environ, "LOCAL_DEV": "true", "DEBUG": "true"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for server to boot
    time.sleep(4.0)
    
    # Verify server status
    if proc.poll() is not None:
        print("Error: FastAPI server failed to start.")
        stdout, stderr = proc.communicate()
        print(f"Stdout:\n{stdout}\nStderr:\n{stderr}")
        sys.exit(1)
        
    try:
        # Check health endpoint
        r_health = requests.get(f"{url}/health")
        print(f"Health response: {r_health.status_code} - {r_health.json()}")
        
        # Check analysis process endpoint with real PDF
        pdf_path = Path("tests/fixtures/balances_reales/Balance 2017 - Mar Vivo.pdf")
        print(f"Sending balance {pdf_path.name} to {url}/api/v1/analisis/procesar...")
        
        with open(pdf_path, "rb") as f:
            files = {"file_balance": (pdf_path.name, f, "application/pdf")}
            data = {"giro_empresa": "Comercio"}
            
            response = requests.post(
                f"{url}/api/v1/analisis/procesar",
                files=files,
                data=data,
                timeout=45
            )
            
        print(f"Process response status: {response.status_code}")
        if response.status_code == 200:
            res_json = response.json()
            print("Smoke test passed! JSON Response keys:")
            print(list(res_json.keys()))
            print(f"Accounts classified: {len(res_json.get('classified', []))}")
            print(f"Accounts ignored: {len(res_json.get('ignored', []))}")
            sys.exit(0)
        else:
            print(f"Smoke test failed! Response: {response.text}")
            sys.exit(1)
            
    except Exception as e:
        print(f"Smoke test encountered error: {e}")
        sys.exit(1)
        
    finally:
        print("Stopping FastAPI server...")
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    run_smoke_test()
