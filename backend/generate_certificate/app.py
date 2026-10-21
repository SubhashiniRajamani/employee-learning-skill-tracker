
import os
import uuid
from io import BytesIO
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
ses = boto3.client("ses")
SENDER_EMAIL = os.environ["SES_SENDER_EMAIL"]
employees = dynamodb.Table(os.environ["EMPLOYEES_TABLE"])
courses = dynamodb.Table(os.environ["COURSES_TABLE"])
completions = dynamodb.Table(os.environ["COMPLETIONS_TABLE"])
certificates = dynamodb.Table(os.environ["CERTIFICATES_TABLE"])

BUCKET_NAME = os.environ["CERTIFICATES_BUCKET"]


def make_pdf(name, title, date, certificate_id):
    buffer = BytesIO()

    pdf = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)

    pdf.setStrokeColor(colors.HexColor("#174A7E"))
    pdf.setLineWidth(6)
    pdf.rect(25, 25, width - 50, height - 50)

    pdf.setFillColor(colors.HexColor("#174A7E"))
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawCentredString(
        width / 2, height - 125,
        "CERTIFICATE OF COMPLETION"
    )

    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica", 16)
    pdf.drawCentredString(
        width / 2, height - 185,
        "This certificate is proudly awarded to"
    )

    pdf.setFont("Helvetica-Bold", 25)
    pdf.drawCentredString(
        width / 2, height - 240,
        name
    )

    pdf.setFont("Helvetica", 16)
    pdf.drawCentredString(
        width / 2, height - 290,
        "for successfully completing the course"
    )

    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawCentredString(
        width / 2, height - 335,
        title
    )

    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(
        width / 2, 155,
        f"Completion Date: {date}"
    )
    pdf.drawCentredString(
        width / 2, 128,
        f"Certificate ID: {certificate_id}"
    )

    pdf.setFont("Helvetica-Oblique", 12)
    pdf.drawCentredString(
        width / 2, 80,
        "Employee Learning and Skill Certification Tracker"
    )

    pdf.showPage()
    pdf.save()

    return buffer.getvalue()


def lambda_handler(event, context):
    employee_id = event.get("employee_id")
    course_id = event.get("course_id")

    if not employee_id or not course_id:
        return {"error": "Employee ID and course ID required"}

    key = {
        "employee_id": employee_id,
        "course_id": course_id
    }

    completion = completions.get_item(
        Key=key,
        ConsistentRead=True
    ).get("Item")

    if not completion or completion.get("status") != "PASSED":
        return {"error": "Employee has not passed this course"}

    employee = employees.get_item(
        Key={"employee_id": employee_id}
    ).get("Item")

    course = courses.get_item(
        Key={"course_id": course_id}
    ).get("Item")

    if not employee or not course:
        return {"error": "Employee or course not found"}

    # Claim a unique certificate ID once per completion.
    certificate_id = completion.get("certificate_id")

    if not certificate_id:
        new_id = str(uuid.uuid4())

        try:
            completions.update_item(
                Key=key,
                UpdateExpression="SET certificate_id = :id",
                ConditionExpression=(
                    "#status = :passed AND "
                    "attribute_not_exists(certificate_id)"
                ),
                ExpressionAttributeNames={
                    "#status": "status"
                },
                ExpressionAttributeValues={
                    ":id": new_id,
                    ":passed": "PASSED"
                }
            )
            certificate_id = new_id

        except ClientError as error:
            if error.response["Error"]["Code"] != (
                "ConditionalCheckFailedException"
            ):
                raise

            updated = completions.get_item(
                Key=key,
                ConsistentRead=True
            ).get("Item", {})

            certificate_id = updated.get("certificate_id")

            if not certificate_id:
                return {"error": "Certificate issuance conflict"}

    completion_date = completion.get(
        "completion_date",
        datetime.now(timezone.utc).date().isoformat()
    )

    employee_name = employee.get(
        "name", employee_id
    )
    course_title = course.get(
        "title", course_id
    )

    pdf_bytes = make_pdf(
        employee_name,
        course_title,
        completion_date,
        certificate_id
    )

    s3_key = f"certificates/{employee_id}/{course_id}.pdf"

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=pdf_bytes,
        ContentType="application/pdf",
        ServerSideEncryption="AES256"
    )

    certificates.put_item(
        Item={
            "certificate_id": certificate_id,
            "employee_id": employee_id,
            "course_id": course_id,
            "employee_name": employee_name,
            "course_title": course_title,
            "completion_date": completion_date,
            "s3_key": s3_key,
            "status": "VALID"
        }
    )


    # Generate a temporary download link (24 hours).
    download_url = s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": BUCKET_NAME,
            "Key": s3_key,
            "ResponseContentDisposition":
                f'attachment; filename="{course_id}.pdf"'
        },
        ExpiresIn=86400
    )

    recipient_email = employee.get("email")

    if not recipient_email:
        return {
            "status": "CERTIFICATE_CREATED",
            "certificate_id": certificate_id,
            "email_status": "SKIPPED",
            "reason": "Employee email missing"
        }

    try:
        ses.send_email(
            Source=SENDER_EMAIL,
            Destination={
                "ToAddresses": [recipient_email]
            },
            Message={
                "Subject": {
                    "Data": f"Your SkillTrack Certificate - {course_title}"
                },
                "Body": {
                    "Text": {
                        "Data": (
                            f"Congratulations {employee_name}!\n\n"
                            f"You successfully completed: {course_title}\n"
                            f"Completion Date: {completion_date}\n"
                            f"Certificate ID: {certificate_id}\n\n"
                            f"Download your certificate:\n{download_url}\n\n"
                            "This download link expires in 24 hours.\n"
                            "You can request a new link later."
                        )
                    }
                }
            }
        )

        certificates.update_item(
            Key={"certificate_id": certificate_id},
            UpdateExpression=(
                "SET email_status = :sent, emailed_at = :now"
            ),
            ExpressionAttributeValues={
                ":sent": "SENT",
                ":now": datetime.now(timezone.utc).isoformat()
            }
        )

    except ClientError as error:
        return {
            "status": "CERTIFICATE_CREATED",
            "certificate_id": certificate_id,
            "email_status": "FAILED",
            "reason": error.response["Error"]["Code"]
        }


    return {
        "status": "CERTIFICATE_CREATED",
        "certificate_id": certificate_id,
        "employee_id": employee_id,
        "course_id": course_id,
        "s3_bucket": BUCKET_NAME,
        "s3_key": s3_key,
        "email_status": "SENT"
    }
