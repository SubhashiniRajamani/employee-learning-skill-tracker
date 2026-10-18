
import json
import os
from datetime import date, datetime, timezone
from urllib.parse import quote

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

db = boto3.resource("dynamodb")
ses = boto3.client("ses")

courses = db.Table(os.environ["COURSES_TABLE"])
employees = db.Table(os.environ["EMPLOYEES_TABLE"])
assignments = db.Table(os.environ["ASSIGNMENTS_TABLE"])

SENDER = os.environ["SES_SENDER_EMAIL"]
APP_URL = os.environ["APP_URL"].rstrip("/")


def response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def is_hr_admin(event):
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

    return (
        claims.get("token_use") == "access"
        and "HR_ADMIN" in groups
    )


def send_assignment_email(employee, course, due_date):
    course_id = quote(course["course_id"], safe="")
    link = f"{APP_URL}/employee/course/{course_id}"

    body = (
        f"Hello {employee['name']},\n\n"
        f"You have been assigned a new course.\n\n"
        f"Course: {course['title']}\n"
        f"Due date: {due_date}\n\n"
        f"Course link: {link}\n\n"
        "Please complete your training before the due date.\n\n"
        "SkillTrack LMS"
    )

    ses.send_email(
        Source=SENDER,
        Destination={
            "ToAddresses": [employee["email"]]
        },
        Message={
            "Subject": {
                "Data": f"Training Assigned: {course['title']}",
                "Charset": "UTF-8",
            },
            "Body": {
                "Text": {
                    "Data": body,
                    "Charset": "UTF-8",
                }
            },
        },
    )


def lambda_handler(event, context):
    if not is_hr_admin(event):
        return response(403, {"error": "HR Admin only"})

    try:
        body = json.loads(event.get("body") or "{}")
    except (ValueError, TypeError):
        return response(400, {"error": "Invalid JSON"})

    if not isinstance(body, dict):
        return response(400, {"error": "Expected JSON object"})

    course_id = body.get("course_id")
    employee_ids = body.get("employee_ids")
    role = body.get("role")
    due_date = body.get("due_date")

    if not isinstance(course_id, str) or not course_id:
        return response(400, {"error": "course_id required"})

    try:
        deadline = date.fromisoformat(due_date)
        if deadline < date.today():
            return response(400, {"error": "Due date is in the past"})
    except (ValueError, TypeError):
        return response(400, {"error": "Use YYYY-MM-DD due date"})

    has_ids = isinstance(employee_ids, list) and bool(employee_ids)
    has_role = isinstance(role, str) and bool(role.strip())

    if has_ids == has_role:
        return response(400, {
            "error": "Provide either employee_ids or role"
        })

    if has_ids and (
        len(employee_ids) > 25
        or any(
            not isinstance(x, str) or not x.strip()
            for x in employee_ids
        )
    ):
        return response(400, {
            "error": "Provide 1 to 25 valid employee IDs"
        })

    course = courses.get_item(
        Key={"course_id": course_id}
    ).get("Item")

    if not course:
        return response(404, {"error": "Course not found"})

    selected = []

    if has_ids:
        for employee_id in dict.fromkeys(employee_ids):
            employee = employees.get_item(
                Key={"employee_id": employee_id}
            ).get("Item")

            if employee:
                selected.append(employee)

    
    else:
        if role not in course.get("assigned_roles", []):
            return response(400, {
                "error": "Role is not eligible for this course"
            })

        result = employees.scan(
            FilterExpression=Attr("role").eq(role)
        )
        selected.extend(result.get("Items", []))

        while "LastEvaluatedKey" in result:
            result = employees.scan(
                FilterExpression=Attr("role").eq(role),
                ExclusiveStartKey=result["LastEvaluatedKey"],
            )
            selected.extend(result.get("Items", []))




        if len(selected) > 25:
            return response(400, {
                "error": "This demo supports up to 25 employees per assignment request"
            })

    if not selected:
        return response(404, {
            "error": "No matching employees"
        })

    results = []

    for employee in selected:
        emp_id = employee["employee_id"]

        item = {
            "employee_id": emp_id,
            "course_id": course_id,
            "assigned_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "due_date": deadline.isoformat(),
            "status": "NOT_STARTED",
            "email_status": "PENDING",
        }

        try:
            assignments.put_item(
                Item=item,
                ConditionExpression=(
                    "attribute_not_exists(employee_id)"
                    " AND attribute_not_exists(course_id)"
                ),
            )
        except ClientError as exc:
            if (
                exc.response["Error"]["Code"]
                == "ConditionalCheckFailedException"
            ):
                results.append({
                    "employee_id": emp_id,
                    "result": "ALREADY_ASSIGNED",
                })
                continue
            raise

        try:
            send_assignment_email(employee, course, due_date)
            email_status = "SENT"
        except ClientError:
            email_status = "FAILED"

        assignments.update_item(
            Key={
                "employee_id": emp_id,
                "course_id": course_id,
            },
            UpdateExpression="SET email_status = :s",
            ExpressionAttributeValues={":s": email_status},
        )

        results.append({
            "employee_id": emp_id,
            "result": "CREATED",
            "email_status": email_status,
        })

    return response(200, {
        "message": "Assignment request processed",
        "course_id": course_id,
        "results": results,
    })

