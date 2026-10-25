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
      setError("La contraseña debe tener al menos 12 caracteres.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setIsSubmitting(true);
    try {
      await apiClient.post("/auth/password-reset/confirm", { token, new_password: password });
      setSuccess(true);
    } catch {
      setError("El enlace no es válido o ya venció. Pide uno nuevo.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>Nueva contraseña</h1>
        {success ? (
          <p>
            Tu contraseña cambió. <a href="/login">Iniciar sesión</a>
          </p>
        ) : (
          <>
            <label>
              Contraseña nueva
              <PasswordInput value={password} onChange={(e) => setPassword(e.target.value)} required minLength={12} />
            </label>
            <label>
              Confirma la contraseña
              <PasswordInput value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required minLength={12} />
            </label>
            {error && <p className="form-error">{error}</p>}
            <button type="submit" disabled={isSubmitting || !token}>
              {isSubmitting ? "Guardando…" : "Guardar contraseña"}
            </button>
          </>
        )}
      </form>
    </div>
  );
}
