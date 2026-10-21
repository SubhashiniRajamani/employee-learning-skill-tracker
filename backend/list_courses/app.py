
import json
import os

import boto3

dynamodb = boto3.resource("dynamodb")
courses_table = dynamodb.Table(os.environ["COURSES_TABLE"])


def lambda_handler(event, context):
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )

    groups = claims.get("cognito:groups", [])

    if isinstance(groups, str):
        groups = [
            group.strip()
            for group in groups.strip("[]").split(",")
        ]

    if claims.get("token_use") != "access" or "HR_ADMIN" not in groups:
        return {
            "statusCode": 403,
            "body": json.dumps({"error": "HR Admin only"}),
        }

    items = []
    scan_kwargs = {}

    while True:
        response = courses_table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break

        scan_kwargs["ExclusiveStartKey"] = last_key

    result = [
        {
            "course_id": course["course_id"],
            "title": course.get("title", ""),
            "passing_score": int(course.get("passing_score", 0)),
        }
        for course in items
    ]

    result.sort(key=lambda course: course["title"].lower())

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
        },
        "body": json.dumps({"courses": result}),
    }
