import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { PasswordInput } from "@/components/PasswordInput";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (password.length < 12) {
      setError("Password must be at least 12 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setIsSubmitting(true);
    try {
      await apiClient.post("/auth/password-reset/confirm", { token, new_password: password });
      setSuccess(true);
    } catch {
      setError("This reset link is invalid or has expired.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>Reset password</h1>
        {success ? (
          <p>
            Your password was changed. <a href="/login">Sign in</a>
          </p>
        ) : (
          <>
            <label>
              New password
              <PasswordInput value={password} onChange={(e) => setPassword(e.target.value)} required minLength={12} />
            </label>
            <label>
              Confirm password
              <PasswordInput value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required minLength={12} />
            </label>
            {error && <p className="form-error">{error}</p>}
            <button type="submit" disabled={isSubmitting || !token}>
              {isSubmitting ? "Saving..." : "Set new password"}
            </button>
          </>
        )}
      </form>
    </div>
  );
}
