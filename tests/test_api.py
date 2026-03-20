import requests

BASE_URL = "http://127.0.0.1:5000"

def test_endpoint(path):
    try:
        response = requests.get(f"{BASE_URL}{path}")

        # Check status code
        if response.status_code != 200:
            print(f"[FAIL] {path} → Status {response.status_code}")
            return

        # Try parsing JSON
        try:
            data = response.json()
        except Exception:
            print(f"[FAIL] {path} → Response is not valid JSON")
            return

        # Validate structure
        if isinstance(data, dict):
            if "data" in data or "endpoints" in data:
                print(f"[PASS] {path} → 200 OK + valid structure")
            else:
                print(f"[WARN] {path} → 200 OK but unexpected structure")
        else:
            print(f"[WARN] {path} → 200 OK but not a JSON object")

    except Exception as e:
        print(f"[ERROR] {path} → {e}")


def run_tests():
    print("Running API tests...\n")

    test_endpoint("/telemetry/latest")
    test_endpoint("/telemetry/stats")
    test_endpoint("/telemetry/history")

    print("\nTests completed.")


if __name__ == "__main__":
    run_tests()