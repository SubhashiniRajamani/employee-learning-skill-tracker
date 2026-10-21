
import json
import os
import hashlib
import hmac
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

db = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")
CERTIFICATE_FUNCTION_NAME = os.environ["CERTIFICATE_FUNCTION_NAME"]
employees = db.Table(os.environ["EMPLOYEES_TABLE"])
assignments = db.Table(os.environ["ASSIGNMENTS_TABLE"])
quizzes = db.Table(os.environ["QUIZZES_TABLE"])
completions = db.Table(os.environ["COMPLETIONS_TABLE"])
courses = db.Table(os.environ["COURSES_TABLE"])


def response(status, data):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store"
        },
        "body": json.dumps(data)
    }


def hash_answer(answer):
    # Must match scripts/seed_data.py
    normalized = answer.strip().casefold()
    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


def find_employee(cognito_sub):
    found = []
    args = {
        "FilterExpression": Attr(
            "cognito_sub"
        ).eq(cognito_sub)
    }

    while True:
        result = employees.scan(**args)
        found.extend(result.get("Items", []))

        if len(found) > 1:
            return None, "DUPLICATE"

        last = result.get("LastEvaluatedKey")
        if not last:
            break

        args["ExclusiveStartKey"] = last

    if not found:
        return None, "NOT_FOUND"

    return found[0], None


def get_questions(course_id):
    items = []
    args = {
        "KeyConditionExpression": Key(
            "course_id"
        ).eq(course_id)
    }

    while True:
        result = quizzes.query(**args)
        items.extend(result.get("Items", []))

        last = result.get("LastEvaluatedKey")
        if not last:
            break

        args["ExclusiveStartKey"] = last

    return items


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
            g.strip()
            for g in groups.strip("[]").split(",")
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
            "error": "Missing identity"
        })

    employee, lookup_error = find_employee(cognito_sub)

    if lookup_error == "DUPLICATE":
        return response(409, {
            "error": "Duplicate employee identity mapping"
        })

    if not employee:
        return response(403, {
            "error": "Employee account not linked"
        })

    employee_id = employee["employee_id"]

    course_id = (
        event.get("pathParameters") or {}
    ).get("course_id")

    if not course_id:
        return response(400, {
            "error": "Course ID required"
        })

    assignment_key = {
        "employee_id": employee_id,
        "course_id": course_id
    }

    assignment = assignments.get_item(
        Key=assignment_key,
        ConsistentRead=True
    ).get("Item")

    if not assignment:
        return response(403, {
            "error": "Course not assigned"
        })

    course = courses.get_item(
        Key={"course_id": course_id}
    ).get("Item")

    if not course:
        return response(404, {
            "error": "Course not found"
        })

    try:
        body = json.loads(event.get("body") or "{}")
    except (ValueError, TypeError):
        return response(400, {
            "error": "Invalid JSON"
        })

    if not isinstance(body, dict):
        return response(400, {
            "error": "Request body must be an object"
        })

    answers = body.get("answers")
    if not isinstance(answers, list):
        return response(400, {
            "error": "answers must be a list"
        })

    questions = get_questions(course_id)

    if not questions:
        return response(404, {
            "error": "Quiz questions not found"
        })

    question_map = {
        q["question_id"]: q
        for q in questions
    }

    submitted = {}

    for entry in answers:
        if not isinstance(entry, dict):
            return response(400, {
                "error": "Invalid answer entry"
            })

        qid = entry.get("question_id")
        answer = entry.get("answer")

        if (
            not isinstance(qid, str)
            or not isinstance(answer, str)
            or qid in submitted
        ):
            return response(400, {
                "error": "Invalid or duplicate answer"
            })

        submitted[qid] = answer

    if set(submitted) != set(question_map):
        return response(400, {
            "error": "Answer every question exactly once"
        })

    correct_count = 0

    for qid, question in question_map.items():
        answer = submitted[qid].strip()

        if answer not in question["options"]:
            return response(400, {
                "error": f"Invalid option for {qid}"
            })

        candidate_hash = hash_answer(answer)

        if hmac.compare_digest(
            candidate_hash,
            question["correct_answer_hash"]
        ):
            correct_count += 1

    score = round(
        (correct_count / len(questions)) * 100,
        2
    )

    passing_score = float(course["passing_score"])
    passed = score >= passing_score

    status = "PASSED" if passed else "FAILED"
    now = datetime.now(timezone.utc).isoformat()

    key = {
        "employee_id": employee_id,
        "course_id": course_id
    }

    # Atomically enforce maximum 3 submissions
    # and prevent submissions after passing.
    try:
        result = completions.update_item(
            Key=key,
            UpdateExpression=(
                "SET attempt_count = "
                "if_not_exists(attempt_count, :zero) + :one, "
                "#status = :status, "
                "score = :score, "
                "last_attempt_at = :now"
                + (", completion_date = :date" if passed else "")
            ),
            ConditionExpression=(
                "(attribute_not_exists(attempt_count) "
                "OR attempt_count < :max_attempts) "
                "AND (attribute_not_exists(#status) "
                "OR #status <> :passed)"
            ),
            ExpressionAttributeNames={
                "#status": "status"
            },
            
            ExpressionAttributeValues={
                ":zero": 0,
                ":one": 1,
                ":max_attempts": 3,
                ":status": status,
                ":passed": "PASSED",
                ":score": Decimal(str(score)),
                ":now": now,
                **({":date": now[:10]} if passed else {}),
            },

            ReturnValues="ALL_NEW"
        )

    except ClientError as error:
        if (
            error.response["Error"]["Code"]
            == "ConditionalCheckFailedException"
        ):
            return response(403, {
                "error": (
                    "Quiz already passed or "
                    "maximum 3 attempts reached"
                )
            })
        raise

    attempts_used = int(
        result["Attributes"]["attempt_count"]
    )

    # Update course assignment progress.
    # Never downgrade a previously passed assignment.
    try:
        assignments.update_item(
            Key=assignment_key,
            UpdateExpression="SET #status = :status",
            ConditionExpression=(
                "attribute_exists(employee_id) "
                "AND attribute_exists(course_id) "
                "AND (attribute_not_exists(#status) "
                "OR #status <> :passed)"
            ),
            ExpressionAttributeNames={
                "#status": "status"
            },
            ExpressionAttributeValues={
                ":status": status,
                ":passed": "PASSED"
            }
        )
    except ClientError as error:
        if (
            error.response["Error"]["Code"]
            != "ConditionalCheckFailedException"
        ):
            raise
    
    # Automatically generate a certificate after passing.
    certificate_status = "NOT_ELIGIBLE"

    if passed:
        try:
            invocation = lambda_client.invoke(
                FunctionName=CERTIFICATE_FUNCTION_NAME,
                InvocationType="Event",
                Payload=json.dumps({
                    "employee_id": employee_id,
                    "course_id": course_id
                }).encode("utf-8")
            )

            certificate_status = (
                "PROCESSING"
                if invocation["StatusCode"] == 202
                else "TRIGGER_FAILED"
            )

        except ClientError as error:
            print(
                "Certificate invocation failed:",
                error.response["Error"]["Code"]
            )
            certificate_status = "TRIGGER_FAILED"

    return response(200, {
        "employee_id": employee_id,
        "course_id": course_id,
        "score": score,
        "correct_answers": correct_count,
        "total_questions": len(questions),
        "passing_score": passing_score,
        "status": status,
        "attempt_count": attempts_used,
        "attempts_remaining": 3 - attempts_used,
        "certificate_status": certificate_status
    })

