import { useRef, useState } from "react";

interface SignaturePadProps {
  onCapture: (dataUrl: string) => void;
  disabled?: boolean;
  /** Avisa la firma dibujada al levantar el dedo (null al borrar), para que otro
   * botón la guarde. Con `hideCapture` no se muestra el botón «Firmar». */
  onDraw?: (dataUrl: string | null) => void;
  hideCapture?: boolean;
}

/** Minimal canvas-based signature capture — technician/customer sign directly
 * in the app (confirmed requirement: replaces the paper signature section). */
export function SignaturePad({ onCapture, disabled, onDraw, hideCapture }: SignaturePadProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const drawing = useRef(false);
  const traced = useRef(false);
  const [hasStroke, setHasStroke] = useState(false);

  const getContext = () => canvasRef.current?.getContext("2d") ?? null;

  // El lienzo se muestra a todo el ancho de su contenedor, así que su tamaño
  // en pantalla no es el de sus píxeles: se escala la posición del dedo para
  // que el trazo caiga donde se toca.
  const pointerPos = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    return {
      x: ((e.clientX - rect.left) * canvas.width) / rect.width,
      y: ((e.clientY - rect.top) * canvas.height) / rect.height,
    };
  };

  const start = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (disabled) return;
    drawing.current = true;
    const ctx = getContext();
    const { x, y } = pointerPos(e);
    ctx?.beginPath();
    ctx?.moveTo(x, y);
  };

  const move = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current || disabled) return;
    const ctx = getContext();
    const { x, y } = pointerPos(e);
    if (ctx) {
      ctx.lineWidth = 3;
      ctx.lineCap = "round";
      ctx.strokeStyle = "#111827";
      ctx.lineTo(x, y);
      ctx.stroke();
    }
    traced.current = true;
    setHasStroke(true);
  };

  const end = () => {
    if (drawing.current && traced.current && canvasRef.current) onDraw?.(canvasRef.current.toDataURL("image/png"));
    drawing.current = false;
  };

  const clear = () => {
    const canvas = canvasRef.current;
    const ctx = getContext();
    if (canvas && ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    traced.current = false;
    setHasStroke(false);
    onDraw?.(null);
  };

  const capture = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    onCapture(canvas.toDataURL("image/png"));
  };

  return (
    <div>
      <canvas
        ref={canvasRef}
        width={600}
        height={220}
        className="signature-canvas"
        aria-label="Recuadro para firmar"
        style={{ border: "1px solid #d1d5db", borderRadius: 8, background: "white", touchAction: "none", width: "100%", maxWidth: 600, height: "auto" }}
        onPointerDown={start}
        onPointerMove={move}
        onPointerUp={end}
        onPointerLeave={end}
      />
      <div className="inline-form" style={{ marginTop: "0.5rem" }}>
        <button type="button" className="acta-btn is-quiet" onClick={clear} disabled={disabled || !hasStroke}>
          Borrar
        </button>
        {!hideCapture && (
          <button type="button" className="acta-btn is-primary" onClick={capture} disabled={disabled || !hasStroke}>
            Firmar
          </button>
        )}
      </div>
    </div>
  );
}
