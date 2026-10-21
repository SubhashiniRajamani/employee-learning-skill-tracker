
import { useCallback, useEffect, useState } from "react";
import { fetchAuthSession } from "aws-amplify/auth";
import QuizPage from "./QuizPage";
import "./EmployeeDashboard.css";

const API_URL =
  "https://hmp7xht4bf.execute-api.ap-south-1.amazonaws.com";

type Assignment = {
  course_id: string;
  title: string;
  description: string;
  external_video_url: string;
  passing_score: number | null;
  due_date: string;
  status: string;
  overdue: boolean;
  attempt_count: number;
  score: number | null;
  certificate_id: string | null;
};

type EmployeeData = {
  employee_id: string;
  employee_name: string;
  assignments: Assignment[];
  summary: {
    assigned: number;
    passed: number;
    overdue: number;
  };
};

export default function EmployeeDashboard() {
  const [data, setData] = useState<EmployeeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [selectedQuiz, setSelectedQuiz] = useState<{
    courseId: string;
    courseTitle: string;
  } | null>(null);

  const [downloadingCourseId, setDownloadingCourseId] =
    useState<string | null>(null);

  // Load the signed-in employee's assigned courses.
  const loadAssignments = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const session = await fetchAuthSession();
      const token = session.tokens?.accessToken?.toString();

      if (!token) {
        throw new Error("Please sign in again.");
      }

      const response = await fetch(`${API_URL}/me/assignments`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.error ||
            result.message ||
            `Assignments API returned HTTP ${response.status}`
        );
      }

      setData(result as EmployeeData);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load employee assignments."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  // Load assignments when the dashboard opens.
  useEffect(() => {
    void loadAssignments();
  }, [loadAssignments]);

  // Request a secure, temporary certificate download link.
  async function downloadCertificate(courseId: string) {
    if (downloadingCourseId !== null) return;

    setDownloadingCourseId(courseId);
    setError("");

    try {
      const session = await fetchAuthSession();
      const token = session.tokens?.accessToken?.toString();

      if (!token) {
        throw new Error("Your session expired. Please sign in again.");
      }

      const response = await fetch(
        `${API_URL}/me/certificates/${encodeURIComponent(
          courseId
        )}/download`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.error ||
            result.message ||
            `Certificate API returned HTTP ${response.status}`
        );
      }

      if (
        typeof result.download_url !== "string" ||
        !result.download_url.startsWith("https://")
      ) {
        throw new Error("Certificate download URL is unavailable.");
      }

      // The backend generates a temporary S3 download URL.
      // No AWS access keys are stored in the React frontend.
      const link = document.createElement("a");
      link.href = result.download_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";

      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to download certificate."
      );
    } finally {
      setDownloadingCourseId(null);
    }
  }

  // Display quiz if an eligible course was selected.
  if (selectedQuiz) {
    return (
      <QuizPage
        courseId={selectedQuiz.courseId}
        courseTitle={selectedQuiz.courseTitle}
        onClose={() => {
          setSelectedQuiz(null);
          void loadAssignments();
        }}
        onFinished={() => {
          void loadAssignments();
        }}
      />
    );
  }

  if (loading) {
    return <p>Loading your assigned courses...</p>;
  }

  if (error && !data) {
    return (
      <section className="employee-dashboard">
        <h2>My Learning Dashboard</h2>
        <p className="error-text" role="alert">
          {error}
        </p>

        <button
          type="button"
          className="employee-refresh"
          onClick={() => void loadAssignments()}
        >
          Retry
        </button>
      </section>
    );
  }

  if (!data) {
    return <p>No employee information available.</p>;
  }

  return (
    <section className="employee-dashboard">
      <div className="employee-heading">
        <div>
          <h2>My Learning Dashboard</h2>
          <p>
            {data.employee_name} · Employee ID: {data.employee_id}
          </p>
        </div>

        <button
          type="button"
          className="employee-refresh"
          onClick={() => void loadAssignments()}
        >
          Refresh
        </button>
      </div>

      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}

      <div className="employee-stats">
        <div className="employee-stat-card">
          <span>Assigned Courses</span>
          <strong>{data.summary.assigned}</strong>
        </div>

        <div className="employee-stat-card">
          <span>Passed</span>
          <strong>{data.summary.passed}</strong>
        </div>

        <div className="employee-stat-card">
          <span>Overdue</span>
          <strong className="employee-overdue-count">
            {data.summary.overdue}
          </strong>
        </div>
      </div>

      <h3>My Courses</h3>

      {data.assignments.length === 0 ? (
        <div className="employee-empty">
          No courses have been assigned to you yet.
        </div>
      ) : (
        <div className="employee-course-grid">
          {data.assignments.map((course) => {
            const passed = course.status === "PASSED";

            const attemptsUsed = Number(
              course.attempt_count || 0
            );

            const attemptsRemaining = Math.max(
              0,
              3 - attemptsUsed
            );

            return (
              <article
                key={course.course_id}
                className={
                  course.overdue
                    ? "employee-course-card employee-course-overdue"
                    : "employee-course-card"
                }
              >
                <div className="employee-course-top">
                  <span className="employee-course-id">
                    {course.course_id}
                  </span>

                  <span
                    className={
                      course.overdue
                        ? "employee-status employee-status-overdue"
                        : passed
                          ? "employee-status employee-status-passed"
                          : "employee-status employee-status-other"
                    }
                  >
                    {course.overdue
                      ? "OVERDUE"
                      : course.status.replaceAll("_", " ")}
                  </span>
                </div>

                <h4>{course.title}</h4>

                <p>
                  {course.description ||
                    "No description available."}
                </p>

                <div className="employee-course-details">
                  <div>
                    <span>Due Date</span>
                    <strong>
                      {course.due_date || "Not set"}
                    </strong>
                  </div>

                  <div>
                    <span>Score</span>
                    <strong>
                      {course.score == null
                        ? "Not graded"
                        : `${course.score}%`}
                    </strong>
                  </div>

                  <div>
                    <span>Attempts Remaining</span>
                    <strong>
                      {attemptsRemaining} of 3
                    </strong>
                  </div>
                </div>

                <div className="employee-course-actions">
                  {course.external_video_url && (
                    <a
                      href={course.external_video_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="employee-link"
                    >
                      Watch Course Video ↗
                    </a>
                  )}

                  {passed ? (
                    course.certificate_id ? (
                      <div className="certificate-actions">
                        <a
                          href={`${API_URL}/verify/${encodeURIComponent(
                            course.certificate_id
                          )}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="employee-certificate-link"
                        >
                          Verify Certificate ↗
                        </a>

                        <button
                          type="button"
                          className="employee-refresh"
                          disabled={
                            downloadingCourseId ===
                            course.course_id
                          }
                          onClick={() =>
                            void downloadCertificate(
                              course.course_id
                            )
                          }
                        >
                          {downloadingCourseId ===
                          course.course_id
                            ? "Preparing PDF..."
                            : "Download PDF ↓"}
                        </button>
                      </div>
                    ) : (
                      <span>
                        Certificate is being prepared.
                      </span>
                    )
                  ) : attemptsRemaining === 0 ? (
                    <span className="employee-attempts-exhausted">
                      Maximum quiz attempts reached
                    </span>
                  ) : (
                    <button
                      className="employee-refresh"
                      type="button"
                      onClick={() =>
                        setSelectedQuiz({
                          courseId: course.course_id,
                          courseTitle: course.title,
                        })
                      }
                    >
                      Take Quiz →
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
