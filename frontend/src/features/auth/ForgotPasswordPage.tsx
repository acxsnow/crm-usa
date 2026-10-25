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
      setMessage("Si hay una cuenta activa con ese correo, te enviamos un enlace para recuperar la contraseña.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>¿Olvidaste tu contraseña?</h1>
        {message ? (
          <p>{message}</p>
        ) : (
          <>
            <label>
              Correo
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
            </label>
            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Enviando…" : "Enviar enlace"}
            </button>
          </>
        )}
        <a className="auth-link" href="/login">
          Volver a iniciar sesión
        </a>
      </form>
    </div>
  );
}
