
import json
import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

db = boto3.resource("dynamodb")
sns = boto3.client("sns")

assignments_table = db.Table(os.environ["ASSIGNMENTS_TABLE"])
completions_table = db.Table(os.environ["COMPLETIONS_TABLE"])
employees_table = db.Table(os.environ["EMPLOYEES_TABLE"])
courses_table = db.Table(os.environ["COURSES_TABLE"])

SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]


def scan_all(table):
    items = []
    options = {}

    while True:
        result = table.scan(**options)
        items.extend(result.get("Items", []))

        if "LastEvaluatedKey" not in result:
            break

        options["ExclusiveStartKey"] = result["LastEvaluatedKey"]

    return items


def lambda_handler(event, context):
    today = datetime.now(timezone.utc).date().isoformat()

    employees = {
        e["employee_id"]: e
        for e in scan_all(employees_table)
    }

    courses = {
        c["course_id"]: c
        for c in scan_all(courses_table)
    }

    completions = {
        (c["employee_id"], c["course_id"]): c
        for c in scan_all(completions_table)
    }

    overdue = []

    for assignment in scan_all(assignments_table):
        employee_id = assignment["employee_id"]
        course_id = assignment["course_id"]

        due_date = assignment.get("due_date", "")

        completion = completions.get(
            (employee_id, course_id), {}
        )

        status = completion.get(
            "status",
            assignment.get("status", "NOT_STARTED")
        )

        if (
            due_date
            and due_date < today
            and status != "PASSED"
        ):
            employee = employees.get(employee_id, {})
            course = courses.get(course_id, {})

            overdue.append({
                "employee_id": employee_id,
                "employee_name": employee.get(
                    "name", employee_id
                ),
                "department": employee.get(
                    "department", "Unknown"
                ),
                "course_id": course_id,
                "course_title": course.get(
                    "title", course_id
                ),
                "due_date": due_date,
                "status": status
            })

    overdue.sort(
        key=lambda item: (
            item["department"],
            item["employee_name"],
            item["course_id"]
        )
    )

    lines = [
        "SkillTrack Weekly Overdue Training Report",
        f"Report Date (UTC): {today}",
        f"Total Overdue Assignments: {len(overdue)}",
        ""
    ]

    for item in overdue:
        lines.append(
            f"{item['employee_name']} "
            f"({item['employee_id']}, {item['department']})"
        )
        lines.append(
            f"Course: {item['course_title']} "
            f"({item['course_id']})"
        )
        lines.append(
            f"Due: {item['due_date']} | "
            f"Status: {item['status']}"
        )
        lines.append("")

    if not overdue:
        lines.append(
            "No overdue training assignments found."
        )

    message = "\n".join(lines)

    result = sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject="SkillTrack Weekly Overdue Training Report",
        Message=message
    )

    return {
        "status": "REPORT_SENT",
        "report_date": today,
        "overdue_count": len(overdue),
        "sns_message_id": result["MessageId"]
    }
