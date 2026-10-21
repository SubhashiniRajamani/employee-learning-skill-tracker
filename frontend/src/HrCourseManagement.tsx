
import { useState } from "react";
import { fetchAuthSession } from "aws-amplify/auth";
import "./HrCourseManagement.css";
import HrQuizManagement from "./HrQuizManagement";

const API_URL =
  "https://hmp7xht4bf.execute-api.ap-south-1.amazonaws.com";

type Props = {
  onChanged?: () => void;
};

async function postToApi(
  path: string,
  payload: Record<string, unknown>
) {
  const session = await fetchAuthSession();
  const token = session.tokens?.accessToken?.toString();

  if (!token) {
    throw new Error("Session expired. Please sign in again.");
  }

  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      data.error || data.message || `HTTP ${response.status}`
    );
  }

  return data;
}

export default function HrCourseManagement({ onChanged }: Props) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [videoUrl, setVideoUrl] = useState("");
  const [passingScore, setPassingScore] = useState("80");
  const [assignedRoles, setAssignedRoles] = useState("");

  const [createdCourseId, setCreatedCourseId] = useState("");

  const [assignCourseId, setAssignCourseId] = useState("");
  const [assignmentType, setAssignmentType] =
    useState<"employees" | "role">("employees");
  const [employeeIds, setEmployeeIds] = useState("");
  const [role, setRole] = useState("");
  const [dueDate, setDueDate] = useState("");

  const [creating, setCreating] = useState(false);
  const [assigning, setAssigning] = useState(false);

  const [courseMessage, setCourseMessage] = useState("");
  const [assignmentMessage, setAssignmentMessage] = useState("");
  const [courseError, setCourseError] = useState("");
  const [assignmentError, setAssignmentError] = useState("");

  async function createCourse(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();

    if (creating) return;

    setCreating(true);
    setCourseMessage("");
    setCourseError("");

    try {
      const data = await postToApi("/courses", {
        title: title.trim(),
        description: description.trim(),
        external_video_url: videoUrl.trim(),
        passing_score: Number(passingScore),
        assigned_roles: assignedRoles
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
      });

      const newId = String(data.course_id);

      setCreatedCourseId(newId);
      setAssignCourseId(newId);

      setCourseMessage(
        `Course created successfully! Course ID: ${newId}`
      );

      setTitle("");
      setDescription("");
      setVideoUrl("");
      setPassingScore("80");
      setAssignedRoles("");

      onChanged?.();
    } catch (error) {
      setCourseError(
        error instanceof Error ? error.message : "Course creation failed."
      );
    } finally {
      setCreating(false);
    }
  }

  async function assignCourse(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();

    if (assigning) return;

    setAssigning(true);
    setAssignmentMessage("");
    setAssignmentError("");

    try {
      const payload: Record<string, unknown> = {
        course_id: assignCourseId.trim(),
        due_date: dueDate,
      };

      if (assignmentType === "employees") {
        const ids = employeeIds
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean);

        if (ids.length === 0) {
          throw new Error("Enter at least one employee ID.");
        }

        payload.employee_ids = ids;
      } else {
        if (!role.trim()) {
          throw new Error("Enter an employee role.");
        }

        payload.role = role.trim();
      }

      const data = await postToApi("/assignments", payload);

      const results = Array.isArray(data.results) ? data.results : [];

      const created = results.filter(
        (item: { result: string }) => item.result === "CREATED"
      ).length;

      const existing = results.filter(
        (item: { result: string }) => item.result === "ALREADY_ASSIGNED"
      ).length;

      const emailsSent = results.filter(
        (item: { email_status?: string }) =>
          item.email_status === "SENT"
      ).length;

      setAssignmentMessage(
        `Assignment processed. New: ${created}. ` +
        `Already assigned: ${existing}. ` +
        `Emails sent: ${emailsSent}.`
      );

      onChanged?.();
    } catch (error) {
      setAssignmentError(
        error instanceof Error ? error.message : "Assignment failed."
      );
    } finally {
      setAssigning(false);
    }
  }

  return (
    <div className="hr-management">
      <h2>HR Course Management</h2>
      <p className="hr-management-subtitle">
        Create training courses and assign them to employees.
      </p>

      <div className="hr-management-grid">
        <section className="hr-management-panel">
          <h3>Create New Course</h3>

          <form onSubmit={(event) => void createCourse(event)}>
            <label htmlFor="course-title">Course Title</label>
            <input
              id="course-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="AWS Cloud Security Advanced"
              required
            />

            <label htmlFor="course-description">Description</label>
            <textarea
              id="course-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Describe the training course"
              rows={3}
              required
            />

            <label htmlFor="course-video">Training Video URL</label>
            <input
              id="course-video"
              type="url"
              value={videoUrl}
              onChange={(event) => setVideoUrl(event.target.value)}
              placeholder="https://www.youtube.com/watch?v=..."
              required
            />

            <label htmlFor="course-score">Passing Score (%)</label>
            <input
              id="course-score"
              type="number"
              min="0"
              max="100"
              value={passingScore}
              onChange={(event) => setPassingScore(event.target.value)}
              required
            />

            <label htmlFor="course-roles">
              Eligible Employee Roles (comma separated)
            </label>
            <input
              id="course-roles"
              value={assignedRoles}
              onChange={(event) => setAssignedRoles(event.target.value)}
              placeholder="Developer, DevOps"
            />

            <button
              type="submit"
              className="hr-management-button"
              disabled={creating}
            >
              {creating ? "Creating..." : "Create Course"}
            </button>
          </form>

          {courseError && (
            <p className="hr-management-error" role="alert">
              {courseError}
            </p>
          )}

          {courseMessage && (
            <p className="hr-management-success" role="status">
              {courseMessage}
            </p>
          )}

          {createdCourseId && (
            <button
              type="button"
              className="hr-management-secondary"
              onClick={() => setAssignCourseId(createdCourseId)}
            >
              Use Newly Created Course for Assignment
            </button>
          )}
        </section>

        <section className="hr-management-panel">
          <h3>Assign Training</h3>

          <form onSubmit={(event) => void assignCourse(event)}>
            <label htmlFor="assign-course-id">Course ID</label>
            <input
              id="assign-course-id"
              value={assignCourseId}
              onChange={(event) =>
                setAssignCourseId(event.target.value)
              }
              placeholder="COURSE001"
              required
            />

            <label htmlFor="assignment-type">Assign By</label>
            <select
              id="assignment-type"
              value={assignmentType}
              onChange={(event) =>
                setAssignmentType(
                  event.target.value as "employees" | "role"
                )
              }
            >
              <option value="employees">Employee IDs</option>
              <option value="role">Employee Role</option>
            </select>

            {assignmentType === "employees" ? (
              <>
                <label htmlFor="employee-ids">
                  Employee IDs (comma separated)
                </label>
                <input
                  id="employee-ids"
                  value={employeeIds}
                  onChange={(event) =>
                    setEmployeeIds(event.target.value)
                  }
                  placeholder="EMP001, EMP005"
                  required
                />
              </>
            ) : (
              <>
                <label htmlFor="employee-role">Employee Role</label>
                <input
                  id="employee-role"
                  value={role}
                  onChange={(event) => setRole(event.target.value)}
                  placeholder="Developer"
                  required
                />
                <small>
                  The role must be listed in the course's eligible roles.
                </small>
              </>
            )}

            <label htmlFor="due-date">Due Date</label>
            <input
              id="due-date"
              type="date"
              value={dueDate}
              onChange={(event) => setDueDate(event.target.value)}
              required
            />

            <button
              type="submit"
              className="hr-management-button"
              disabled={assigning}
            >
              {assigning
                ? "Assigning..."
                : "Assign Course & Send Email"}
            </button>
          </form>

          {assignmentError && (
            <p className="hr-management-error" role="alert">
              {assignmentError}
            </p>
          )}

          {assignmentMessage && (
            <p className="hr-management-success" role="status">
              {assignmentMessage}
            </p>
          )}

          <p className="hr-management-note">
            New assignments are stored in DynamoDB. The backend
            sends notification emails through Amazon SES.
            Existing assignments are not overwritten.
          </p>
        </section>
      </div>
      <HrQuizManagement />
    </div>
  );
}
