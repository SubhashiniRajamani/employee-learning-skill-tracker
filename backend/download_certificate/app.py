
import json
import os
from urllib.parse import quote

import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

employees = dynamodb.Table(os.environ["EMPLOYEES_TABLE"])
completions = dynamodb.Table(os.environ["COMPLETIONS_TABLE"])

BUCKET = os.environ["CERTIFICATES_BUCKET"]


def reply(status, data):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(data),
    }


def scan_all(table):
    results = []
    params = {}

    while True:
        page = table.scan(**params)
        results.extend(page.get("Items", []))

        last_key = page.get("LastEvaluatedKey")
        if not last_key:
            return results

        params["ExclusiveStartKey"] = last_key


def lambda_handler(event, context):
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )

    raw_groups = claims.get("cognito:groups", [])

    if isinstance(raw_groups, str):
        groups = [
            value.strip().strip('"').strip("'")
            for value in raw_groups.strip("[]").split(",")
        ]
    elif isinstance(raw_groups, list):
        groups = raw_groups
    else:
        groups = []

    if (
        claims.get("token_use") != "access"
        or "EMPLOYEE" not in groups
    ):
        return reply(403, {"error": "Employee access required"})

    user_sub = claims.get("sub")
    if not user_sub:
        return reply(401, {"error": "Missing user identity"})

    course_id = (
        (event.get("pathParameters") or {}).get("course_id") or ""
    )

    if not course_id:
        return reply(400, {"error": "Course ID required"})

    # Resolve employee identity from the verified Cognito subject.
    matches = [
        employee
        for employee in scan_all(employees)
        if employee.get("cognito_sub") == user_sub
    ]

    if len(matches) != 1:
        return reply(403, {"error": "Employee identity unavailable"})

    employee_id = matches[0]["employee_id"]

    # Only the employee's own passed completion is eligible.
    completion = completions.get_item(
        Key={
            "employee_id": employee_id,
            "course_id": course_id,
        },
        ConsistentRead=True,
    ).get("Item")

    if (
        not completion
        or completion.get("status") != "PASSED"
        or not completion.get("certificate_id")
    ):
        return reply(404, {
            "error": "No completed certificate found for this course"
        })

    object_key = (
        f"certificates/{employee_id}/{course_id}.pdf"
    )

    try:
        s3.head_object(Bucket=BUCKET, Key=object_key)

        download_name = f"SkillTrack-{course_id}.pdf"

        url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": BUCKET,
                "Key": object_key,
                "ResponseContentDisposition": (
                    f'attachment; filename="{download_name}"'
                ),
                "ResponseContentType": "application/pdf",
            },
            ExpiresIn=900,
        )

        return reply(200, {
            "course_id": course_id,
            "certificate_id": completion["certificate_id"],
            "download_url": url,
            "expires_in_seconds": 900,
        })

    except ClientError as exc:
        code = exc.response["Error"]["Code"]

        if code in ("404", "NoSuchKey", "NotFound"):
            return reply(404, {
                "error": "Certificate PDF is still being prepared"
            })

        print("Certificate S3 error:", code)
        return reply(500, {
            "error": "Unable to prepare certificate download"
        })

