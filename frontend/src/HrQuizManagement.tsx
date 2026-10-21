
import { useState } from "react";
import { fetchAuthSession } from "aws-amplify/auth";
import "./HrCourseManagement.css";

const API_URL =
  "https://hmp7xht4bf.execute-api.ap-south-1.amazonaws.com";

export default function HrQuizManagement() {
  const [courseId, setCourseId] = useState("");
  const [questionId, setQuestionId] = useState("Q001");
  const [question, setQuestion] = useState("");
  const [options, setOptions] = useState(["", "", "", ""]);
  const [correctIndex, setCorrectIndex] = useState("");
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  function updateOption(index: number, value: string) {
    setOptions((previous) =>
      previous.map((option, i) => (i === index ? value : option))
    );
  }

  async function handleSubmit(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;

    setError("");
    setSuccess("");

    const cleanedOptions = options.map((value) => value.trim());

    if (new Set(cleanedOptions).size !== 4) {
      setError("All four answer options must be different.");
      return;
    }

    if (correctIndex === "") {
      setError("Select the correct answer.");
      return;
    }

    setSaving(true);

    try {
      const session = await fetchAuthSession();
      const token = session.tokens?.accessToken?.toString();

      if (!token) {
        throw new Error("Session expired. Sign in again.");
      }

      const response = await fetch(
        `${API_URL}/courses/${encodeURIComponent(
          courseId.trim()
        )}/questions`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            question_id: questionId.trim(),
            question: question.trim(),
            options: cleanedOptions,
            correct_answer: cleanedOptions[Number(correctIndex)],
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error || data.message || `HTTP ${response.status}`
        );
      }

      setSuccess(
        `Question ${data.question_id} saved successfully for ${data.course_id}.`
      );

      setQuestion("");
      setOptions(["", "", "", ""]);
      setCorrectIndex("");

      // Suggest the next ID; HR can change it if necessary.
      const match = questionId.match(/^Q(\d+)$/i);

      if (match) {
        const nextNumber = Number(match[1]) + 1;
        setQuestionId(
          `Q${String(nextNumber).padStart(3, "0")}`
        );
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to save quiz question."
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="hr-management-panel" style={{ marginTop: 24 }}>
      <h3>Manage Quiz Questions</h3>

      <p className="hr-management-note">
        Add multiple-choice questions to a new course before employees
        attempt its quiz. The backend securely hashes the correct answer.
      </p>

      <form onSubmit={(event) => void handleSubmit(event)}>
        <label htmlFor="quiz-course-id">Course ID</label>
        <input
          id="quiz-course-id"
          value={courseId}
          onChange={(event) => setCourseId(event.target.value)}
          placeholder="COURSE-..."
          required
        />

        <label htmlFor="quiz-question-id">Question ID</label>
        <input
          id="quiz-question-id"
          value={questionId}
          onChange={(event) => setQuestionId(event.target.value)}
          placeholder="Q001"
          required
        />

        <label htmlFor="quiz-question">Question</label>
        <textarea
          id="quiz-question"
          rows={3}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Which AWS service manages access permissions?"
          required
        />

        {options.map((option, index) => (
          <div key={index}>
            <label htmlFor={`quiz-option-${index}`}>
              Option {index + 1}
            </label>
            <input
              id={`quiz-option-${index}`}
              value={option}
              onChange={(event) =>
                updateOption(index, event.target.value)
              }
              placeholder={`Answer option ${index + 1}`}
              required
            />
          </div>
        ))}

        <label htmlFor="quiz-correct-answer">Correct Answer</label>
        <select
          id="quiz-correct-answer"
          value={correctIndex}
          onChange={(event) => setCorrectIndex(event.target.value)}
          required
        >
          <option value="">Select the correct option</option>
          {options.map((option, index) => (
            <option
              key={index}
              value={index}
              disabled={!option.trim()}
            >
              Option {index + 1}: {option || "(empty)"}
            </option>
          ))}
        </select>

        <button
          type="submit"
          className="hr-management-button"
          disabled={saving}
        >
          {saving ? "Saving..." : "Save Quiz Question"}
        </button>
      </form>

      {success && (
        <p className="hr-management-success" role="status">
          {success}
        </p>
      )}

      {error && (
        <p className="hr-management-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
