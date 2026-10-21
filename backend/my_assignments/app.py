
import json
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3

dynamodb = boto3.resource("dynamodb")

employees_table = dynamodb.Table(os.environ["EMPLOYEES_TABLE"])
assignments_table = dynamodb.Table(os.environ["ASSIGNMENTS_TABLE"])
courses_table = dynamodb.Table(os.environ["COURSES_TABLE"])
completions_table = dynamodb.Table(os.environ["COMPLETIONS_TABLE"])


def scan_all(table):
    items = []
    kwargs = {}

    while True:
        response = table.scan(**kwargs)
        items.extend(response.get("Items", []))

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break

        kwargs["ExclusiveStartKey"] = last_key

    return items


def json_default(value):
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Unsupported type: {type(value).__name__}")


def reply(status_code, data):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(data, default=json_default),
    }


def lambda_handler(event, context):
    try:
        claims = (
            event.get("requestContext", {})
            .get("authorizer", {})
            .get("jwt", {})
            .get("claims", {})
        )

        cognito_sub = claims.get("sub")
        raw_groups = claims.get("cognito:groups", "")

        if isinstance(raw_groups, list):
            groups = raw_groups
        else:
            groups = [
                group.strip().strip('"').strip("'")
                for group in str(raw_groups).strip("[]").split(",")
            ]

        if not cognito_sub or "EMPLOYEE" not in groups:
            return reply(403, {"message": "Employee access required"})

        employees = scan_all(employees_table)

        employee = next(
            (
                item for item in employees
                if item.get("cognito_sub") == cognito_sub
            ),
            None,
        )

        if not employee:
            return reply(
                404,
                {"message": "Employee record not found"},
            )

        employee_id = employee["employee_id"]

        assignments = [
            item for item in scan_all(assignments_table)
            if item.get("employee_id") == employee_id
        ]

        courses = {
            item["course_id"]: item
            for item in scan_all(courses_table)
        }

        completions = {
            item["course_id"]: item
            for item in scan_all(completions_table)
            if item.get("employee_id") == employee_id
        }

        today = datetime.now(timezone.utc).date().isoformat()
        results = []

        for assignment in assignments:
            course_id = assignment.get("course_id")
            course = courses.get(course_id, {})
            completion = completions.get(course_id, {})

            status = assignment.get("status", "NOT_STARTED")

            if completion.get("status") == "PASSED":
                status = "PASSED"

            due_date = str(assignment.get("due_date") or "")
            overdue = (
                bool(due_date)
                and due_date < today
                and status != "PASSED"
            )

            results.append({
                "course_id": course_id,
                "title": course.get("title", course_id),
                "description": course.get("description", ""),
                "external_video_url": course.get(
                    "external_video_url", ""
                ),
                "passing_score": course.get("passing_score"),
                "due_date": due_date,
                "status": status,
                "overdue": overdue,
                "attempt_count": completion.get(
                    "attempt_count", 0
                ),
                "score": completion.get(
                    "score", assignment.get("score")
                ),
                "certificate_id": completion.get(
                    "certificate_id"
                ),
            })

        results.sort(
            key=lambda item: (
                not item["overdue"],
                item["due_date"] or "9999-12-31",
                item["title"],
            )
        )

        return reply(200, {
            "employee_id": employee_id,
            "employee_name": employee.get(
                "name",
                employee.get("employee_name", employee_id),
            ),
            "assignments": results,
            "summary": {
                "assigned": len(results),
                "passed": sum(
                    item["status"] == "PASSED"
                    for item in results
                ),
                "overdue": sum(
                    item["overdue"] for item in results
                ),
            },
        })

    except Exception as exc:
        print("My assignments error:", repr(exc))
        return reply(
            500,
            {"message": "Unable to retrieve assignments"},
        )
