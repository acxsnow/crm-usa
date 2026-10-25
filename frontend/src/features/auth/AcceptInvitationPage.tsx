import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { PasswordInput } from "@/components/PasswordInput";

export function AcceptInvitationPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (password.length < 12) {
      setError("La contraseña debe tener al menos 12 caracteres.");
      return;
    }
    setIsSubmitting(true);
    try {
      await apiClient.post("/auth/invitations/accept", { token, password });
      // The accept endpoint doesn't return tokens directly (spec: activation, not auto-login),
      // so we redirect to login with the account now active. If tokens were returned we could
      // guardar la sesión y saltar directo al tablero.
      navigate("/login", { replace: true, state: { activated: true } });
    } catch {
      setError("El enlace de la invitación no es válido o ya venció. Pide una invitación nueva.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>Activa tu cuenta</h1>
        <label>
          Elige una contraseña
          <PasswordInput value={password} onChange={(e) => setPassword(e.target.value)} required minLength={12} />
        </label>
        {error && <p className="form-error">{error}</p>}
        <button type="submit" disabled={isSubmitting || !token}>
          {isSubmitting ? "Activando…" : "Activar cuenta"}
        </button>
      </form>
    </div>
  );
}
