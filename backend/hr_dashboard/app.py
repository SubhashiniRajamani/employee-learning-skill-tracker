
import json
import os
from datetime import date
from decimal import Decimal

import boto3

db = boto3.resource("dynamodb")

employees_table = db.Table(os.environ["EMPLOYEES_TABLE"])
courses_table = db.Table(os.environ["COURSES_TABLE"])
assignments_table = db.Table(os.environ["ASSIGNMENTS_TABLE"])
completions_table = db.Table(os.environ["COMPLETIONS_TABLE"])


def scan_all(table):
    items = []
    kwargs = {}

    while True:
        result = table.scan(**kwargs)
        items.extend(result.get("Items", []))

        if "LastEvaluatedKey" not in result:
            break

        kwargs["ExclusiveStartKey"] = result["LastEvaluatedKey"]

    return items


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store"
        },
        "body": json.dumps(
            body,
            default=lambda value: (
                float(value) if isinstance(value, Decimal)
                else str(value)
            )
        )
    }


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

    if (
        claims.get("token_use") != "access"
        or "HR_ADMIN" not in groups
    ):
        return response(403, {
            "error": "HR administrator access required"
        })

    employees = scan_all(employees_table)
    courses = scan_all(courses_table)
    assignments = scan_all(assignments_table)
    completions = scan_all(completions_table)

    employee_map = {
        item["employee_id"]: item
        for item in employees
    }

    course_map = {
        item["course_id"]: item
        for item in courses
    }

    completion_map = {
        (item["employee_id"], item["course_id"]): item
        for item in completions
    }

    today = date.today().isoformat()
    rows = []

    for assignment in assignments:
        employee_id = assignment["employee_id"]
        course_id = assignment["course_id"]

        employee = employee_map.get(employee_id, {})
        course = course_map.get(course_id, {})

        completion = completion_map.get(
            (employee_id, course_id), {}
        )

        status = completion.get(
            "status",
            assignment.get("status", "NOT_STARTED")
        )

        due_date = assignment.get("due_date", "")

        overdue = bool(
            due_date
            and due_date < today
            and status != "PASSED"
        )

        rows.append({
            "employee_id": employee_id,
            "employee_name": employee.get("name", employee_id),
            "department": employee.get("department", "Unknown"),
            "role": employee.get("role", "Unknown"),
            "course_id": course_id,
            "course_title": course.get("title", course_id),
            "status": status,
            "score": completion.get("score"),
            "attempt_count": completion.get("attempt_count", 0),
            "completion_date": completion.get("completion_date"),
            "due_date": due_date,
            "overdue": overdue
        })

    rows.sort(
        key=lambda row: (
            row["employee_id"],
            row["course_id"]
        )
    )

    # Department-wise mandatory skill completion matrix.
    # A course is mandatory for an employee when their
    # role appears in that course's assigned_roles.
    department_stats = {}

    for row in rows:
        course = course_map.get(row["course_id"], {})
        assigned_roles = course.get("assigned_roles", [])

        if isinstance(assigned_roles, str):
            assigned_roles = [assigned_roles]

        if row["role"] not in assigned_roles:
            continue

        department = row["department"]

        if department not in department_stats:
            department_stats[department] = {
                "department": department,
                "mandatory_assignments": 0,
                "completed_assignments": 0,
                "overdue_assignments": 0
            }

        stats = department_stats[department]
        stats["mandatory_assignments"] += 1

        if row["status"] == "PASSED":
            stats["completed_assignments"] += 1

        if row["overdue"]:
            stats["overdue_assignments"] += 1

    department_skill_matrix = []

    for stats in department_stats.values():
        total = stats["mandatory_assignments"]
        completed = stats["completed_assignments"]

        stats["completion_percentage"] = round(
            (completed / total) * 100, 2
        ) if total else 0

        department_skill_matrix.append(stats)

    department_skill_matrix.sort(
        key=lambda item: item["department"]
    )

    return response(200, {
        "employee_count": len(employees),
        "course_count": len(courses),
        "assignment_count": len(rows),
        "passed_count": sum(
            row["status"] == "PASSED"
            for row in rows
        ),
        "overdue_count": sum(
            row["overdue"]
            for row in rows
        ),
        "rows": rows,
        "department_skill_matrix": department_skill_matrix
    })
