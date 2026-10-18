
import json
import os
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["COURSES_TABLE"])


def response(status, data):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(data)
    }


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")

        if not isinstance(body, dict):
            return response(400, {
                "error": "Request body must be an object"
            })

        title = body.get("title", "")
        description = body.get("description", "")
        video_url = body.get("external_video_url", "")
        passing_score = body.get("passing_score")
        assigned_roles = body.get("assigned_roles", [])

        if not isinstance(title, str) or not title.strip():
            return response(400, {
                "error": "Valid course title is required"
            })

        if not isinstance(description, str):
            return response(400, {
                "error": "Description must be text"
            })

        if not isinstance(video_url, str):
            return response(400, {
                "error": "Invalid video URL"
            })

        parsed = urlparse(video_url)
        hostname = (parsed.hostname or "").lower()

        allowed_hosts = {
            "youtube.com",
            "www.youtube.com",
            "youtu.be",
            "www.youtube-nocookie.com",
            "vimeo.com",
            "www.vimeo.com",
            "player.vimeo.com"
        }

        if parsed.scheme != "https" or hostname not in allowed_hosts:
            return response(400, {
                "error": "Provide a valid HTTPS YouTube or Vimeo URL"
            })

        if isinstance(passing_score, bool) or not isinstance(
            passing_score, (int, float)
        ) or not 0 <= passing_score <= 100:
            return response(400, {
                "error": "passing_score must be between 0 and 100"
            })

        if not isinstance(assigned_roles, list) or not all(
            isinstance(role, str) and role.strip()
            for role in assigned_roles
        ):
            return response(400, {
                "error": "assigned_roles must be a list of role names"
            })

        course_id = "COURSE-" + uuid.uuid4().hex[:12].upper()

        item = {
            "course_id": course_id,
            "title": title.strip(),
            "description": description.strip(),
            "external_video_url": video_url,
            "passing_score": int(passing_score),
            "assigned_roles": assigned_roles,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(course_id)"
        )

        return response(201, {
            "message": "Course created successfully",
            "course_id": course_id,
            "title": item["title"]
        })

    except (ValueError, TypeError, json.JSONDecodeError):
        return response(400, {
            "error": "Invalid request data"
        })
