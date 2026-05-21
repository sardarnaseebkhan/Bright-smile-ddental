"""
Sets environment variables on your Railway service using the Railway API.

Usage:
    python scripts/set_railway_vars.py <RAILWAY_API_TOKEN>

Get your token from: https://railway.app/account/tokens  (New Token → copy it)
"""
import sys
import json
import urllib.request
import urllib.error

RAILWAY_API = "https://backboard.railway.app/graphql/v2"

VARS_TO_SET = {
    "RESEND_API_KEY": "re_KFm69fGM_JynaMvZpnrqRxq44ods1z3sa",
    "FROM_EMAIL": "onboarding@resend.dev",
    "CLINIC_OWNER_EMAIL": "khannn762@gmail.com",
    "CLINIC_NAME": "Bright Smiles Dental",
    "CLINIC_ADDRESS": "1234 Main St, McLean, VA 22101",
    "CLINIC_PHONE": "+17035551234",
    "CLINIC_HOURS_MON_FRI": "8:00 AM - 6:00 PM",
    "CLINIC_HOURS_SAT": "9:00 AM - 2:00 PM",
    "CLINIC_HOURS_SUN": "Closed",
    "GOOGLE_CALENDAR_ID": "skip",
}

VARS_TO_REMOVE = ["SMTP_USER", "SMTP_PASSWORD", "SMTP_HOST", "SMTP_PORT"]


def gql(token: str, query: str, variables: dict = None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        RAILWAY_API,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def get_project_and_env(token: str):
    data = gql(token, """
    query {
        me {
            projects {
                edges {
                    node {
                        id
                        name
                        environments {
                            edges {
                                node { id name }
                            }
                        }
                        services {
                            edges {
                                node { id name }
                            }
                        }
                    }
                }
            }
        }
    }
    """)
    projects = data["data"]["me"]["projects"]["edges"]
    if not projects:
        raise RuntimeError("No Railway projects found.")

    # Pick the first project (or find Bright Smile)
    project = None
    for edge in projects:
        p = edge["node"]
        if "smile" in p["name"].lower() or "dental" in p["name"].lower() or "bright" in p["name"].lower():
            project = p
            break
    if not project:
        project = projects[0]["node"]

    print(f"Project: {project['name']} ({project['id']})")

    env_id = project["environments"]["edges"][0]["node"]["id"]
    env_name = project["environments"]["edges"][0]["node"]["name"]
    print(f"Environment: {env_name} ({env_id})")

    service_id = project["services"]["edges"][0]["node"]["id"]
    service_name = project["services"]["edges"][0]["node"]["name"]
    print(f"Service: {service_name} ({service_id})")

    return project["id"], env_id, service_id


def upsert_vars(token: str, project_id: str, env_id: str, service_id: str):
    for name, value in VARS_TO_SET.items():
        data = gql(token, """
        mutation UpsertVar($input: VariableUpsertInput!) {
            variableUpsert(input: $input)
        }
        """, {
            "input": {
                "projectId": project_id,
                "environmentId": env_id,
                "serviceId": service_id,
                "name": name,
                "value": value,
            }
        })
        if "errors" in data:
            print(f"  FAILED {name}: {data['errors']}")
        else:
            display_value = value if "KEY" not in name else value[:8] + "..."
            print(f"  SET {name}={display_value}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    token = sys.argv[1].strip()
    print("\nConnecting to Railway...\n")

    try:
        project_id, env_id, service_id = get_project_and_env(token)
        print("\nSetting environment variables...")
        upsert_vars(token, project_id, env_id, service_id)
        print("\nDone! Railway will redeploy automatically.")
        print("Test email in ~2 minutes: python tests/test_email.py")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode()}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
