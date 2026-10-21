
import { useEffect, useState } from "react";
import {
  signIn,
  confirmSignIn,
  signOut,
  fetchAuthSession,
} from "aws-amplify/auth";

import HrDashboard from "./HrDashboard";
import EmployeeDashboard from "./EmployeeDashboard";
import "./App.css";

type Role = "HR_ADMIN" | "EMPLOYEE";

function App() {
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const [signedInRole, setSignedInRole] = useState<Role | null>(null);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  const [needsNewPassword, setNeedsNewPassword] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Read the authenticated user's Cognito group.
  async function loadUserRole(): Promise<Role | null> {
    const session = await fetchAuthSession();
    const claims = session.tokens?.accessToken.payload;

    if (!claims) {
      return null;
    }

    const rawGroups = claims["cognito:groups"];

    const groups = Array.isArray(rawGroups)
      ? rawGroups.map(String)
      : typeof rawGroups === "string"
        ? rawGroups
            .replace(/[\[\]]/g, "")
            .split(",")
            .map((group) => group.trim())
        : [];

    if (groups.includes("HR_ADMIN")) {
      return "HR_ADMIN";
    }

    if (groups.includes("EMPLOYEE")) {
      return "EMPLOYEE";
    }

    return null;
  }

  // Restore an existing session when the page reloads.
  useEffect(() => {
    async function restoreSession() {
      try {
        const role = await loadUserRole();
        setSignedInRole(role);
      } catch {
        setSignedInRole(null);
      } finally {
        setLoading(false);
      }
    }

    void restoreSession();
  }, []);

  async function completeLogin() {
    const actualRole = await loadUserRole();

    if (!actualRole) {
      await signOut();
      setError("Your account has no permitted SkillTrack role.");
      return;
    }

    if (selectedRole && actualRole !== selectedRole) {
      await signOut();
      setError(
        "This account does not belong to the selected role. " +
          "Please select the correct login."
      );
      return;
    }

    setSignedInRole(actualRole);
    setPassword("");
    setNewPassword("");
    setNeedsNewPassword(false);
    setError("");
  }

  // Sign in with Cognito.
  async function handleLogin(
    event: React.SubmitEvent<HTMLFormElement>
  ) {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      const result = await signIn({
        username: email.trim(),
        password,
        options: {
          authFlowType: "USER_PASSWORD_AUTH",
        },
      });

      if (
        result.nextStep.signInStep ===
        "CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED"
      ) {
        setNeedsNewPassword(true);
        return;
      }

      if (!result.isSignedIn) {
        setError(
          "Additional authentication is required. " +
            "Please share the challenge message so we can add it."
        );
        return;
      }

      await completeLogin();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Login failed."
      );
    } finally {
      setLoading(false);
    }
  }

  // Handle Cognito's first-login password change.
  async function handleNewPassword(
    event: React.SubmitEvent<HTMLFormElement>
  ) {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      const result = await confirmSignIn({
        challengeResponse: newPassword,
      });

      if (result.isSignedIn) {
        await completeLogin();
      } else {
        setError(
          "An additional sign-in step is required."
        );
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to set the new password."
      );
    } finally {
      setLoading(false);
    }
  }

  // Sign out and return to the homepage.
  async function handleLogout() {
    try {
      await signOut();

      setSignedInRole(null);
      setSelectedRole(null);
      setEmail("");
      setPassword("");
      setNewPassword("");
      setNeedsNewPassword(false);
      setError("");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Sign out failed."
      );
    }
  }

  // Loading screen while Cognito restores the session.
  if (loading && !selectedRole && !signedInRole) {
    return (
      <main className="login-page">
        Loading SkillTrack...
      </main>
    );
  }

  return (
    <div className="app">
      {/* Application header */}
      <header className="header">
        <div className="logo">🎓 SkillTrack</div>
        <span>
          Employee Learning & Certification
        </span>
      </header>

      <main className="main">
        {signedInRole ? (
          // Signed-in dashboards
          <div className="signed-in-page">
            <div className="signed-in-header">
              <div>
                <h1>Welcome to SkillTrack</h1>
                <p>
                  Signed in as{" "}
                  <strong>
                    {signedInRole === "HR_ADMIN"
                      ? "HR Administrator"
                      : "Employee"}
                  </strong>
                </p>
              </div>

              <button
                className="primary-button"
                type="button"
                onClick={() => void handleLogout()}
              >
                Sign Out
              </button>
            </div>

            {error && (
              <p className="error-text" role="alert">
                {error}
              </p>
            )}

            {signedInRole === "HR_ADMIN" ? (
              <HrDashboard />
            ) : (
              <EmployeeDashboard />
            )}
          </div>
        ) : !selectedRole ? (
          // Homepage
          <>
            <div className="welcome">
              <span className="eyebrow">
                LEARNING MANAGEMENT SYSTEM
              </span>

              <h1>Welcome to SkillTrack</h1>

              <p>
                Manage employee training, track progress,
                complete courses and earn verified certificates.
              </p>
            </div>

            <div className="role-grid">
              <button
                className="role-card"
                type="button"
                onClick={() => {
                  setSelectedRole("HR_ADMIN");
                  setError("");
                }}
              >
                <span className="role-icon">
                  👩‍💼
                </span>

                <h2>HR Administrator</h2>

                <p>
                  Create courses, assign training and
                  monitor employee learning progress.
                </p>

                <span className="card-action">
                  Continue as HR →
                </span>
              </button>

              <button
                className="role-card"
                type="button"
                onClick={() => {
                  setSelectedRole("EMPLOYEE");
                  setError("");
                }}
              >
                <span className="role-icon">
                  👩‍🎓
                </span>

                <h2>Employee</h2>

                <p>
                  View assigned courses, take quizzes
                  and access your certificates.
                </p>

                <span className="card-action">
                  Continue as Employee →
                </span>
              </button>
            </div>
          </>
        ) : (
          // Cognito login form
          <section className="login-panel">
            <h1>
              {selectedRole === "HR_ADMIN"
                ? "HR Administrator Login"
                : "Employee Login"}
            </h1>

            <p>
              Sign in using your existing AWS Cognito account.
            </p>

            <form
              onSubmit={
                needsNewPassword
                  ? handleNewPassword
                  : handleLogin
              }
            >
              {!needsNewPassword ? (
                <>
                  <label htmlFor="email">
                    Email
                  </label>

                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(event) =>
                      setEmail(event.target.value)
                    }
                    required
                    autoComplete="username"
                  />

                  <label htmlFor="password">
                    Password
                  </label>

                  <input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(event) =>
                      setPassword(event.target.value)
                    }
                    required
                    autoComplete="current-password"
                  />
                </>
              ) : (
                <>
                  <p>
                    Set your new permanent password.
                  </p>

                  <label htmlFor="new-password">
                    New Password
                  </label>

                  <input
                    id="new-password"
                    type="password"
                    value={newPassword}
                    onChange={(event) =>
                      setNewPassword(event.target.value)
                    }
                    required
                    autoComplete="new-password"
                  />
                </>
              )}

              {error && (
                <p className="error-text" role="alert">
                  {error}
                </p>
              )}

              <button
                className="primary-button"
                type="submit"
                disabled={loading}
              >
                {loading
                  ? "Please wait..."
                  : needsNewPassword
                    ? "Set Password"
                    : "Sign In"}
              </button>
            </form>

            <button
              className="back-button"
              type="button"
              onClick={() => {
                setSelectedRole(null);
                setNeedsNewPassword(false);
                setPassword("");
                setNewPassword("");
                setError("");
              }}
            >
              ← Back to Home
            </button>
          </section>
        )}
      </main>

      <footer className="footer">
        SkillTrack • AWS Serverless Learning Platform
      </footer>
    </div>
  );
}

export default App;

