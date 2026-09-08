import { useState, type FormEvent } from "react";
import { apiClient } from "@/lib/apiClient";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const response = await apiClient.post("/auth/password-reset/request", { email });
      setMessage(response.data.message);
    } catch {
      setMessage("If an active account exists for this email, a recovery link has been sent.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>Forgot password?</h1>
        {message ? (
          <p>{message}</p>
        ) : (
          <>
            <label>
              Email
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
            </label>
            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Sending..." : "Send recovery link"}
            </button>
          </>
        )}
        <a className="auth-link" href="/login">
          Back to sign in
        </a>
      </form>
    </div>
  );
}
