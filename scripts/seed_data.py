
import boto3
import hashlib
from datetime import date, timedelta
from botocore.exceptions import ClientError

REGION = "ap-south-1"

db = boto3.resource("dynamodb", region_name=REGION)

tables = {
    "employees": db.Table("skilltrack-employees"),
    "courses": db.Table("skilltrack-courses"),
    "quizzes": db.Table("skilltrack-quizzes"),
    "assignments": db.Table("skilltrack-assignments"),
}

# Use a real, publicly accessible YouTube/Vimeo
# video URL when creating courses through the HR UI.
VIDEO_URL = "https://www.youtube.com/"

employees = [
    {
        "employee_id": "EMP001",
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "department": "Engineering",
        "role": "Developer",
    },
    {
        "employee_id": "EMP002",
        "name": "Bob Smith",
        "email": "bob@example.com",
        "department": "Engineering",
        "role": "DevOps",
    },
    {
        "employee_id": "EMP003",
        "name": "Charlie Brown",
        "email": "charlie@example.com",
        "department": "HR",
        "role": "HR Executive",
    },
    {
        "employee_id": "EMP004",
        "name": "Diana Patel",
        "email": "diana@example.com",
        "department": "Finance",
        "role": "Analyst",
    },
    {
        "employee_id": "EMP005",
        "name": "Ethan Kumar",
        "email": "ethan@example.com",
        "department": "Engineering",
        "role": "Developer",
    },
]

courses = [
    {
        "course_id": "COURSE001",
        "title": "AWS Security Fundamentals",
        "description": "Learn core AWS security concepts.",
        "external_video_url": VIDEO_URL,
        "passing_score": 70,
        "assigned_roles": ["Developer", "DevOps"],
        "mandatory": True,
    },
    {
        "course_id": "COURSE002",
        "title": "Git and GitHub Essentials",
        "description": "Learn version control fundamentals.",
        "external_video_url": VIDEO_URL,
        "passing_score": 75,
        "assigned_roles": ["Developer", "DevOps"],
        "mandatory": True,
    },
    {
        "course_id": "COURSE003",
        "title": "Cybersecurity Awareness",
        "description": "Learn workplace cybersecurity.",
        "external_video_url": VIDEO_URL,
        "passing_score": 80,
        "assigned_roles": ["Developer", "DevOps", "HR Executive", "Analyst"],
        "mandatory": True,
    },
]

question_bank = {
    "COURSE001": [
        ("Which AWS service stores objects?",
         ["EC2", "S3", "Lambda", "SNS"], "S3"),
        ("Which service manages AWS permissions?",
         ["IAM", "S3", "CloudWatch", "SNS"], "IAM"),
        ("Which service runs serverless functions?",
         ["EC2", "RDS", "Lambda", "S3"], "Lambda"),
        ("Which AWS service stores NoSQL data?",
         ["DynamoDB", "SES", "SNS", "CloudFront"], "DynamoDB"),
        ("What does MFA improve?",
         ["Storage", "Authentication", "Billing", "Latency"], "Authentication"),
    ],
    "COURSE002": [
        ("Which command initializes a Git repository?",
         ["git init", "git push", "git log", "git clone"], "git init"),
        ("Which command records staged changes?",
         ["git status", "git add", "git commit", "git fetch"], "git commit"),
        ("Which command displays the working tree status?",
         ["git status", "git merge", "git push", "git init"], "git status"),
        ("Which command downloads a repository?",
         ["git reset", "git clone", "git tag", "git branch"], "git clone"),
        ("Which command uploads local commits?",
         ["git pull", "git push", "git diff", "git show"], "git push"),
    ],
    "COURSE003": [
        ("What is phishing?",
         ["A backup process", "A social engineering attack", "Encryption", "A firewall"],
         "A social engineering attack"),
        ("Which password is strongest?",
         ["123456", "password", "Company123", "T9#vL2!qR8@z"], "T9#vL2!qR8@z"),
        ("What should you do with a suspicious email link?",
         ["Click it", "Forward widely", "Report it", "Reply with password"], "Report it"),
        ("What does MFA stand for?",
         ["Multi-Factor Authentication", "Main File Access", "Managed Firewall Access", "Multi-File Application"],
         "Multi-Factor Authentication"),
        ("Which connection is safer on public Wi-Fi?",
         ["Unencrypted HTTP", "Approved VPN", "Unknown hotspot", "Open network"],
         "Approved VPN"),
    ],
}

def hash_answer(answer):
    # The quiz grading Lambda must use exactly
    # the same normalization and hashing algorithm.
    normalized = answer.strip().casefold()
    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()

def insert_if_missing(table, item):
    # Prevent overwriting progress on subsequent runs.
    key_name = list(table.key_schema)
    condition_parts = []
    names = {}

    for index, key in enumerate(key_name):
        alias = f"#k{index}"
        names[alias] = key["AttributeName"]
        condition_parts.append(f"attribute_not_exists({alias})")

    try:
        table.put_item(
            Item=item,
            ConditionExpression=" AND ".join(condition_parts),
            ExpressionAttributeNames=names,
        )
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise

def seed():
    counts = {
        "employees": 0,
        "courses": 0,
        "quizzes": 0,
        "assignments": 0,
    }

    print("Seeding SkillTrack LMS in", REGION)

    for employee in employees:
        if insert_if_missing(tables["employees"], employee):
            counts["employees"] += 1

    for course in courses:
        if insert_if_missing(tables["courses"], course):
            counts["courses"] += 1

    for course_id, questions in question_bank.items():
        for index, (question, options, correct) in enumerate(questions, 1):
            item = {
                "course_id": course_id,
                "question_id": f"Q{index:03d}",
                "question": question,
                "options": options,
                "correct_answer_hash": hash_answer(correct),
            }
            if insert_if_missing(tables["quizzes"], item):
                counts["quizzes"] += 1

    today = date.today()

    for employee in employees:
        for course in courses:
            # An overdue example for the dashboard.
            days_until_due = (
                -2 if employee["employee_id"] == "EMP005"
                and course["course_id"] == "COURSE003"
                else 14
            )

            item = {
                "employee_id": employee["employee_id"],
                "course_id": course["course_id"],
                "assigned_at": today.isoformat(),
                "due_date": (today + timedelta(days=days_until_due)).isoformat(),
                "status": "NOT_STARTED",
            }

            if insert_if_missing(tables["assignments"], item):
                counts["assignments"] += 1

    print("\nNew records created:")
    for name, count in counts.items():
        print(f"  {name}: {count}")

    print("\nDatabase seed completed successfully.")
    print("Note: Completion and certificate records will be")
    print("created later by the actual LMS workflow.")

if __name__ == "__main__":
    seed()
