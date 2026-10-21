
import json
import os

import boto3

dynamodb = boto3.resource("dynamodb")
certificates = dynamodb.Table(
    os.environ["CERTIFICATES_TABLE"]
)


def response(status_code, data):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store"
        },
        "body": json.dumps(data)
    }


def lambda_handler(event, context):
    path = event.get("pathParameters") or {}
    certificate_id = path.get("cert_id", "").strip()

    if not certificate_id or len(certificate_id) > 100:
        return response(400, {
            "valid": False,
            "message": "Invalid certificate ID"
        })

    result = certificates.get_item(
        Key={"certificate_id": certificate_id},
        ConsistentRead=True
    )

    certificate = result.get("Item")

    if not certificate:
        return response(200, {
            "valid": False,
            "message": "Certificate not found"
        })

    if certificate.get("status") != "VALID":
        return response(200, {
            "valid": False,
            "message": "Certificate is not valid"
        })

    return response(200, {
        "valid": True,
        "certificate_id": certificate_id,
        "employee_name": certificate.get("employee_name"),
        "course_title": certificate.get("course_title"),
        "completion_date": certificate.get("completion_date"),
        "message": "Certificate verified successfully"
    })
