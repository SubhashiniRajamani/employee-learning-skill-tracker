
import hashlib
import json
import os

import boto3
from botocore.exceptions import ClientError

db = boto3.resource("dynamodb")

quizzes = db.Table(os.environ["QUIZZES_TABLE"])
courses = db.Table(os.environ["COURSES_TABLE"])


def reply(status, data):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(data),
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
            group.strip().strip('"').strip("'")
            for group in groups.strip("[]").split(",")
        ]

    if (
        claims.get("token_use") != "access"
        or "HR_ADMIN" not in groups
    ):
        return reply(403, {"error": "HR Admin only"})

    course_id = (event.get("pathParameters") or {}).get(
        "course_id"
    )

    if not course_id:
        return reply(400, {"error": "Course ID required"})

    if not courses.get_item(
        Key={"course_id": course_id}
    ).get("Item"):
        return reply(404, {"error": "Course not found"})

    try:
        body = json.loads(event.get("body") or "{}")
    except (ValueError, TypeError):
        return reply(400, {"error": "Invalid JSON"})

    if not isinstance(body, dict):
        return reply(400, {"error": "Expected JSON object"})

    question_id = body.get("question_id")
    question = body.get("question")
    options = body.get("options")
    correct_answer = body.get("correct_answer")

    if (
        not isinstance(question_id, str)
        or not question_id.strip()
        or not isinstance(question, str)
        or not question.strip()
        or not isinstance(options, list)
        or len(options) != 4
        or any(
            not isinstance(option, str) or not option.strip()
            for option in options
        )
        or len(set(options)) != 4
        or not isinstance(correct_answer, str)
        or correct_answer not in options
    ):
        return reply(
            400,
            {"error": "Provide a question ID, question, four unique options and a matching correct answer"},
        )

    # Match the normalization used by SubmitQuizFunction.
    normalized = correct_answer.strip().casefold()
    answer_hash = hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()

    item = {
        "course_id": course_id,
        "question_id": question_id.strip(),
        "question": question.strip(),
        "options": options,
        "correct_answer_hash": answer_hash,
    }

    try:
        quizzes.put_item(
            Item=item,
            ConditionExpression=(
                "attribute_not_exists(course_id) "
                "AND attribute_not_exists(question_id)"
            ),
        )
    except ClientError as exc:
        if (
            exc.response["Error"]["Code"]
            == "ConditionalCheckFailedException"
        ):
            return reply(
                409,
                {"error": "Question ID already exists for this course"},
            )
        raise

    return reply(201, {
        "message": "Question created successfully",
        "course_id": course_id,
        "question_id": question_id.strip(),
    })
