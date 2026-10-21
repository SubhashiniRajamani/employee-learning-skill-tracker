
# SkillTrack — Employee Learning and Skill Certification Tracker

A serverless Learning Management System (LMS) built using AWS, Python, React, and TypeScript.

SkillTrack enables HR administrators to create training courses, assign learning activities, manage quizzes, track employee progress, and monitor skill completion. Employees can watch training videos, complete quizzes, and download verifiable PDF certificates after passing.

## Features

### HR Administrator

- Secure login using Amazon Cognito
- Create training courses with video links and passing scores
- Assign courses to individual employees or eligible job roles
- Send course assignment notification emails through Amazon SES
- Create multiple-choice quiz questions
- View employee training progress and course completion status
- Monitor overdue assignments
- View department-level skill completion percentages
- Receive scheduled weekly overdue-training alerts

### Employee

- Secure login using Amazon Cognito
- View assigned courses and due dates
- Access external training videos
- Take multiple-choice quizzes
- Receive immediate quiz results
- Maximum three attempts per course, enforced by the backend
- Receive PDF certificates after passing
- Download certificates securely using temporary S3 links
- Verify certificates using a public verification endpoint

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite |
| Authentication | Amazon Cognito |
| API | Amazon API Gateway HTTP API |
| Backend | AWS Lambda, Python |
| Database | Amazon DynamoDB |
| Certificate Storage | Amazon S3 |
| Email Notifications | Amazon SES |
| Overdue Alerts | Amazon SNS |
| Scheduling | Amazon EventBridge Scheduler |
| Infrastructure as Code | AWS SAM, CloudFormation |
| CI | GitHub Actions |

## System Architecture

```text
                  HR Administrator / Employee
                             |
                             v
                     React + TypeScript
                             |
                             v
                       Amazon Cognito
                             |
                             v
                   Amazon API Gateway
                       (JWT protected)
                             |
                             v
                        AWS Lambda
                             |
          +------------------+------------------+
          |                  |                  |
          v                  v                  v
     DynamoDB              Amazon S3        Amazon SES
  Courses, Employees,    Private PDF        Assignment and
  Assignments, Quizzes,  Certificates       Certificate Emails
  Completions, Certs
                             ^
                             |
                     Certificate Lambda

  EventBridge Scheduler --> Overdue Alert Lambda --> Amazon SNS
```

## AWS Resources

The application is deployed in the AWS `ap-south-1` region.

Main DynamoDB tables:

- `skilltrack-employees`
- `skilltrack-courses`
- `skilltrack-assignments`
- `skilltrack-quizzes`
- `skilltrack-completions`
- `skilltrack-certificates`

The infrastructure is managed using the root `template.yaml` AWS SAM template.

## API Endpoints

| Method | Endpoint | Access |
|---|---|---|
| POST | `/courses` | HR Admin |
| POST | `/assignments` | HR Admin |
| POST | `/courses/{course_id}/questions` | HR Admin |
| GET | `/hr/dashboard` | HR Admin |
| GET | `/me/assignments` | Employee |
| GET | `/courses/{course_id}/quiz` | Employee |
| POST | `/courses/{course_id}/submit` | Employee |
| GET | `/me/certificates/{course_id}/download` | Employee |
| GET | `/verify/{cert_id}` | Public |

Protected endpoints use Cognito JWT authentication. Backend functions also enforce the relevant application role.

## Quiz and Grading

HR administrators create multiple-choice questions for each course.

The correct answer is normalized and hashed using SHA-256 before storage in DynamoDB.

The employee quiz endpoint does not return the correct answer hash.

When an employee submits answers, the backend validates the submitted options, calculates the score, and records the result.

Employees may attempt a course quiz up to three times. After a passing result, additional submissions are blocked.

## Certificate Generation

After a successful quiz:

1. The backend records the passing result.
2. A certificate-generation Lambda creates a PDF certificate.
3. The PDF is stored in a private S3 bucket.
4. Certificate metadata is saved in DynamoDB.
5. The employee is notified using Amazon SES.
6. The employee can request a temporary certificate download link.
7. The certificate can be independently verified by its unique certificate ID.

Certificate downloads are restricted to the authenticated certificate owner.

## Overdue Training Notifications

An EventBridge schedule invokes the overdue-alert Lambda weekly.

The Lambda checks overdue training records and publishes an alert through Amazon SNS.

HR administrators can monitor overdue training in the dashboard.

## Local Development

### Requirements

- Node.js and npm
- Python
- AWS CLI
- AWS SAM CLI
- An AWS account with the required services configured

### Start the Frontend

```bash
cd frontend
npm ci
npm run dev
```

Open:

http://localhost:5173/

The frontend communicates with the configured AWS API Gateway endpoint.

### Build the Frontend

```bash
cd frontend
npm run build
```

### Validate the Backend

From the project root:

```bash
python -m compileall -q backend
sam validate --lint
```

### Deploy Infrastructure

Deploy from the project root using AWS SAM:

```bash
sam build
sam deploy --guided
```

AWS credentials and deployment parameters must be configured separately. Do not commit passwords, AWS access keys, authentication tokens, or private configuration values.

## CI Pipeline

GitHub Actions runs checks when changes are pushed or submitted through pull requests.

The workflow is defined at:

`.github/workflows/ci.yml`

It performs:

1. Installation of frontend dependencies
2. React and TypeScript production build
3. Python backend syntax validation

The CI workflow does not automatically deploy AWS resources.

## Demonstration Data

The system includes a demonstration dataset with five employees and multiple training courses.

Sample scenarios include:

- New course creation
- Course assignment with email notification
- HR quiz question creation
- Employee quiz submission
- Failed quiz attempts
- Successful quiz completion
- PDF certificate generation
- Certificate download and verification
- Department skill-tracking dashboard

## Security

- Cognito authentication for HR and employees
- JWT authorization at API Gateway
- Backend role checks
- Employee-specific certificate access control
- Private S3 certificate storage
- Short-lived presigned download URLs
- Server-side quiz grading and attempt limits
- Correct answer hashes not exposed by quiz APIs
- AWS IAM permissions for Lambda access

## Current Deployment

AWS Region: `ap-south-1`

Infrastructure Stack: `skilltrack-lms`

API endpoint:

https://hmp7xht4bf.execute-api.ap-south-1.amazonaws.com

The React frontend is run locally using Vite. A public frontend hosting deployment is not included in this repository's current setup.

## Project Structure

```text
employee-learning-skill-tracker/
├── .github/workflows/
│   └── ci.yml
├── backend/
│   ├── create_course/
│   ├── assign_course/
│   ├── add_quiz_questions/
│   ├── get_quiz/
│   ├── submit_quiz/
│   ├── my_assignments/
│   ├── hr_dashboard/
│   ├── generate_certificate/
│   ├── download_certificate/
│   ├── verify_certificate/
│   └── overdue_alerts/
├── frontend/
│   └── src/
├── scripts/
├── template.yaml
└── README.md
```

## Future Improvements

- Host the React frontend publicly using AWS Amplify Hosting
- Add quiz versioning and lock questions once attempts begin
- Add automated integration and security tests
- Add pagination for larger employee datasets
- Add a course catalog with search and filtering

## Author

Subhashini Rajamani

## Project Status

Core application implemented and tested with demonstration data. AWS infrastructure deployed using AWS SAM.
