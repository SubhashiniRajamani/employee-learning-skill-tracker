
import { useEffect, useState } from "react";
import { fetchAuthSession } from "aws-amplify/auth";
import "./HrDashboard.css";
import HrCourseManagement from "./HrCourseManagement";

const API_URL =
  "https://hmp7xht4bf.execute-api.ap-south-1.amazonaws.com";

type TrainingRow = {
  employee_id: string;
  employee_name: string;
  department: string;
  role: string;
  course_id: string;
  course_title: string;
  status: string;
  score: number | null;
  attempt_count: number;
  completion_date: string | null;
  due_date: string;
  overdue: boolean;
};

type DepartmentStat = {
  department: string;
  mandatory_assignments: number;
  completed_assignments: number;
  overdue_assignments: number;
  completion_percentage: number;
};

type DashboardData = {
  employee_count: number;
  course_count: number;
  assignment_count: number;
  passed_count: number;
  overdue_count: number;
  rows: TrainingRow[];
  department_skill_matrix: DepartmentStat[];
};

export default function HrDashboard() {
  const [dashboard, setDashboard] =
    useState<DashboardData | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadDashboard() {
    setLoading(true);
    setError("");

    try {
      const session = await fetchAuthSession();
      const token = session.tokens?.accessToken?.toString();

      if (!token) {
        throw new Error("Please sign in again.");
      }

      const response = await fetch(`${API_URL}/hr/dashboard`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(
          `Dashboard API returned HTTP ${response.status}`
        );
      }

      const data: DashboardData = await response.json();
      setDashboard(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load dashboard"
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

  if (loading) {
    return <p>Loading HR dashboard...</p>;
  }

  if (error) {
    return (
      <section className="hr-dashboard">
        <h2>HR Dashboard</h2>
        <p className="error-text" role="alert">{error}</p>
        <button className="primary-button" onClick={() => void loadDashboard()}>
          Retry
        </button>
      </section>
    );
  }

  if (!dashboard) {
    return <p>No dashboard data available.</p>;
  }

  return (
    <section className="hr-dashboard">
      <div className="dashboard-heading">
        <div>
          <h2>HR Training Dashboard</h2>
          <p>Employee learning and certification overview</p>
        </div>

        <button
          className="refresh-button"
          onClick={() => void loadDashboard()}
        >
          Refresh
        </button>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <span>Employees</span>
          <strong>{dashboard.employee_count}</strong>
        </div>

        <div className="stat-card">
          <span>Courses</span>
          <strong>{dashboard.course_count}</strong>
        </div>

        <div className="stat-card">
          <span>Assignments</span>
          <strong>{dashboard.assignment_count}</strong>
        </div>

        <div className="stat-card">
          <span>Passed</span>
          <strong>{dashboard.passed_count}</strong>
        </div>

        <div className="stat-card overdue-stat">
          <span>Overdue</span>
          <strong>{dashboard.overdue_count}</strong>
        </div>
      </div>

      <div className="dashboard-section">
        <h3>Department Skill Completion</h3>

        {dashboard.department_skill_matrix.map((department) => (
          <div
            key={department.department}
            className="department-item"
          >
            <div className="department-label">
              <strong>{department.department}</strong>
              <span>
                {department.completed_assignments}/
                {department.mandatory_assignments}
                {" — "}
                {department.completion_percentage}%
              </span>
            </div>

            <div className="progress-track">
              <div
                className="progress-fill"
                style={{
                  width: `${Math.max(
                    0,
                    Math.min(100, department.completion_percentage)
                  )}%`,
                }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="dashboard-section">
        <h3>Employee Training Status</h3>

        <div className="table-scroll">
          <table className="training-table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Department</th>
                <th>Course</th>
                <th>Status</th>
                <th>Score</th>
                <th>Due Date</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.rows.map((row) => (
                <tr
                  key={`${row.employee_id}-${row.course_id}`}
                  className={row.overdue ? "overdue-row" : ""}
                >
                  <td>{row.employee_name}</td>
                  <td>{row.department}</td>
                  <td>{row.course_title}</td>
                  <td>
                    <span className={
                      row.overdue
                        ? "status-pill status-overdue"
                        : row.status === "PASSED"
                          ? "status-pill status-passed"
                          : "status-pill status-other"
                    }>
                      {row.overdue
                        ? "OVERDUE"
                        : row.status.replaceAll("_", " ")}
                    </span>
                  </td>
                  <td>
                    {row.score == null ? "—" : `${row.score}%`}
                  </td>
                  <td>{row.due_date || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <HrCourseManagement onChanged={() => void loadDashboard()} />
    </section>
  );
}
