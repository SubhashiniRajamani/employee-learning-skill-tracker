
import boto3
import getpass
import json
import urllib.request
import urllib.error
import ssl
import certifi

REGION = "ap-south-1"

cognito = boto3.client("cognito-idp", region_name=REGION)

CLIENT_ID = "22t68sngdl24q7m1och3ihsab4"

API_URL = "https://hmp7xht4bf.execute-api.ap-south-1.amazonaws.com"

username = input("HR Admin email: ").strip()
password = getpass.getpass("Password: ")

auth = cognito.initiate_auth(
    ClientId=CLIENT_ID,
    AuthFlow="USER_PASSWORD_AUTH",
    AuthParameters={
        "USERNAME": username,
        "PASSWORD": password,
    },
)

if auth.get("ChallengeName") == "NEW_PASSWORD_REQUIRED":
    new_password = getpass.getpass("Choose a new password: ")
    challenge_username = auth.get(
        "ChallengeParameters", {}
    ).get("USER_ID_FOR_SRP", username)

    auth = cognito.respond_to_auth_challenge(
        ClientId=CLIENT_ID,
        ChallengeName="NEW_PASSWORD_REQUIRED",
        Session=auth["Session"],
        ChallengeResponses={
            "USERNAME": challenge_username,
            "NEW_PASSWORD": new_password,
        },
    )

if "AuthenticationResult" not in auth:
    print("Additional challenge:", auth.get("ChallengeName"))
    raise SystemExit("Complete the required Cognito login challenge.")

access_token = auth["AuthenticationResult"]["AccessToken"]

print("Login successful!")



course_data = {
    "course_id": "COURSE-93AA91BCCC8F",
    "role": "Developer",
    "due_date": "2026-11-15"
}



request = urllib.request.Request(
    API_URL + "/assignments",
    data=json.dumps(course_data).encode(),
    headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(
    request,
    timeout=30,
    context=ssl.create_default_context(cafile=certifi.where())
    ) as result:
        print("HTTP status:", result.status)
        print(result.read().decode())
except urllib.error.HTTPError as error:
    print("HTTP status:", error.code)
    print(error.read().decode())
