import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { PasswordInput } from "@/components/PasswordInput";
import { Icon } from "@/components/ui/Icon";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const redirectTo = (location.state as { from?: string } | null)?.from ?? "/";

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      navigate(redirectTo, { replace: true });
    } catch {
      setError("El correo o la contraseña no son correctos.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="auth-brand"><span className="auth-logo" aria-hidden="true">P</span><span className="auth-brand-name">PAP CRM</span></div>
        <h1>Iniciar sesión</h1>
        <label>
          Correo
          <span className="auth-input"><Icon name="mail" /><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus /></span>
        </label>
        <label>
          Contraseña
          <span className="auth-input"><Icon name="lock" /><PasswordInput value={password} onChange={(e) => setPassword(e.target.value)} required /></span>
        </label>
        {error && <p className="form-error">{error}</p>}
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Entrando…" : "Entrar"}
        </button>
        <a className="auth-link" href="/forgot-password">
          ¿Olvidaste tu contraseña?
        </a>
      </form>
    </div>
  );
}
