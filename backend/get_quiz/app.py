
import json
import os

import boto3
from boto3.dynamodb.conditions import Key, Attr

db = boto3.resource("dynamodb")

employees = db.Table(os.environ["EMPLOYEES_TABLE"])
assignments = db.Table(os.environ["ASSIGNMENTS_TABLE"])
quizzes = db.Table(os.environ["QUIZZES_TABLE"])
completions = db.Table(os.environ["COMPLETIONS_TABLE"])
courses = db.Table(os.environ["COURSES_TABLE"])


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
        },
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    # API Gateway must authenticate the JWT.
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

    if (
        claims.get("token_use") != "access"
        or "EMPLOYEE" not in groups
    ):
        return response(403, {
            "error": "Employee access required"
        })

    cognito_sub = claims.get("sub")

    if not cognito_sub:
        return response(401, {
            "error": "Missing authenticated identity"
        })

    course_id = (
        event.get("pathParameters") or {}
    ).get("course_id")

    if not course_id:
        return response(400, {
            "error": "course_id is required"
        })

    # Resolve authenticated user to employee record.
    matching_employees = []

    scan_args = {
        "FilterExpression": Attr("cognito_sub").eq(
            cognito_sub
        )
    }

    while True:
        result = employees.scan(**scan_args)
        matching_employees.extend(result.get("Items", []))

        if len(matching_employees) > 1:
            return response(409, {
                "error": "Duplicate identity mapping"
            })

        last_key = result.get("LastEvaluatedKey")

        if not last_key:
            break

        scan_args["ExclusiveStartKey"] = last_key

    if not matching_employees:
        return response(403, {
            "error": "Employee account not linked"
        })

    employee = matching_employees[0]
    employee_id = employee["employee_id"]

    # Verify course is assigned to this employee.
    assignment = assignments.get_item(
        Key={
            "employee_id": employee_id,
            "course_id": course_id,
        }
    ).get("Item")

    if not assignment:
        return response(403, {
            "error": "Course not assigned to employee"
        })

    # Do not allow the quiz after passing or
    # using all three attempts.
    completion = completions.get_item(
        Key={
            "employee_id": employee_id,
            "course_id": course_id,
        }
    ).get("Item", {})

    if completion.get("status") == "PASSED":
        return response(403, {
            "error": "Course already completed"
        })

    attempts = int(completion.get("attempt_count", 0))

    if attempts >= 3:
        return response(403, {
            "error": "Maximum quiz attempts reached"
        })

    course = courses.get_item(
        Key={"course_id": course_id}
    ).get("Item")

    if not course:
        return response(404, {
            "error": "Course not found"
        })

    # DynamoDB Query by course_id.
    questions = []
    query_args = {
        "KeyConditionExpression": Key(
            "course_id"
        ).eq(course_id)
    }

    while True:
        result = quizzes.query(**query_args)
        questions.extend(result.get("Items", []))

        last_key = result.get("LastEvaluatedKey")

        if not last_key:
            break

        query_args["ExclusiveStartKey"] = last_key

    if not questions:
        return response(404, {
            "error": "No quiz questions found"
        })

    # Explicit allowlist prevents answer hash leaks.
    public_questions = [
        {
            "question_id": item["question_id"],
            "question": item["question"],
            "options": item["options"],
        }
        for item in questions
    ]

    return response(200, {
        "course_id": course_id,
        "title": course["title"],
        "passing_score": int(course["passing_score"]),
        "attempts_used": attempts,
        "attempts_remaining": 3 - attempts,
        "questions": public_questions,
    })
