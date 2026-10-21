
import { useEffect, useState } from "react";
import { fetchAuthSession } from "aws-amplify/auth";

const API_URL =
  "https://hmp7xht4bf.execute-api.ap-south-1.amazonaws.com";

type QuizQuestion = {
  question_id: string;
  question: string;
  options: string[];
};

type QuizPageProps = {
  courseId: string;
  courseTitle: string;
  onClose: () => void;
  onFinished: () => void;
};

export default function QuizPage({
  courseId,
  courseTitle,
  onClose,
  onFinished,
}: QuizPageProps) {
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  async function getToken() {
    const session = await fetchAuthSession();
    const token = session.tokens?.accessToken?.toString();

    if (!token) {
      throw new Error("Your session expired. Please sign in again.");
    }

    return token;
  }

  useEffect(() => {
    let active = true;

    async function loadQuiz() {
      setLoading(true);
      setError("");

      try {
        const token = await getToken();

        const response = await fetch(
          `${API_URL}/courses/${encodeURIComponent(courseId)}/quiz`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.message || `HTTP ${response.status}`);
        }

        if (active) {
          setQuestions(data.questions || []);
        }
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error ? err.message : "Unable to load quiz."
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadQuiz();

    return () => {
      active = false;
    };
  }, [courseId]);

  async function submitQuiz() {
    if (questions.some((q) => !answers[q.question_id])) {
      setError("Please answer every question before submitting.");
      return;
    }

    setSubmitting(true);
    setError("");

    try {
      const token = await getToken();

      const response = await fetch(
        `${API_URL}/courses/${encodeURIComponent(courseId)}/submit`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            answers: questions.map((question) => ({
              question_id: question.question_id,
              answer: answers[question.question_id],
            })),
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error || data.message || `HTTP ${response.status}`
        );
      }

      setResult(data);
      onFinished();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to submit quiz."
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <p>Loading quiz...</p>;
  }
  if (error && questions.length === 0) {
  return (
    <section className="dashboard-section">
      <button
        className="back-button"
        type="button"
        onClick={onClose}
      >
        ← Back to My Courses
      </button>

      <h2>{courseTitle}</h2>

      <p className="error-text" role="alert">
        {error.includes("404")
          ? "No quiz questions have been configured for this course yet. Please contact HR."
          : error}
      </p>
    </section>
  );
}
  return (
    <section className="dashboard-section">
      <button className="back-button" onClick={onClose}>
        ← Back to My Courses
      </button>

      <h2>{courseTitle}</h2>
      <p>Answer all questions and submit your quiz.</p>

      {error && <p className="error-text" role="alert">{error}</p>}

      {result ? (
        <div>
          <h3>Quiz submitted successfully!</h3>
          <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
            {JSON.stringify(result, null, 2)}
          </pre>
          <button className="primary-button" onClick={onClose}>
            Return to Dashboard
          </button>
        </div>
      ) : (
        <>
          {questions.map((question, index) => (
            <fieldset
              key={question.question_id}
              style={{
                border: "1px solid #e4e9f2",
                borderRadius: 10,
                padding: 20,
                margin: "20px 0",
              }}
            >
              <legend>
                <strong>
                  {index + 1}. {question.question}
                </strong>
              </legend>

              {question.options.map((option) => (
                <label
                  key={option}
                  style={{
                    display: "flex",
                    gap: 10,
                    alignItems: "center",
                    margin: "12px 0",
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="radio"
                    name={question.question_id}
                    value={option}
                    checked={answers[question.question_id] === option}
                    onChange={() =>
                      setAnswers((previous) => ({
                        ...previous,
                        [question.question_id]: option,
                      }))
                    }
                  />
                  {option}
                </label>
              ))}
            </fieldset>
          ))}

          {questions.length === 0 && !error && (
            <p>No quiz questions are available for this course.</p>
          )}

          <button
            className="primary-button"
            disabled={submitting || questions.length === 0}
            onClick={() => void submitQuiz()}
          >
            {submitting ? "Submitting..." : "Submit Quiz"}
          </button>
        </>
      )}
    </section>
  );
}

