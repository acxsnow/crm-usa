import { useRef, useState } from "react";

interface SignaturePadProps {
  onCapture: (dataUrl: string) => void;
  disabled?: boolean;
}

/** Minimal canvas-based signature capture — technician/customer sign directly
 * in the app (confirmed requirement: replaces the paper signature section). */
export function SignaturePad({ onCapture, disabled }: SignaturePadProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const drawing = useRef(false);
  const [hasStroke, setHasStroke] = useState(false);

  const getContext = () => canvasRef.current?.getContext("2d") ?? null;

  const pointerPos = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
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
      ctx.lineWidth = 2;
      ctx.lineCap = "round";
      ctx.strokeStyle = "#111827";
      ctx.lineTo(x, y);
      ctx.stroke();
    }
    setHasStroke(true);
  };

  const end = () => {
    drawing.current = false;
  };

  const clear = () => {
    const canvas = canvasRef.current;
    const ctx = getContext();
    if (canvas && ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasStroke(false);
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
        width={300}
        height={120}
        style={{ border: "1px solid #d1d5db", borderRadius: 8, background: "white", touchAction: "none" }}
        onPointerDown={start}
        onPointerMove={move}
        onPointerUp={end}
        onPointerLeave={end}
      />
      <div className="inline-form" style={{ marginTop: "0.5rem" }}>
        <button type="button" onClick={clear} disabled={disabled}>
          Limpiar
        </button>
        <button type="button" onClick={capture} disabled={disabled || !hasStroke}>
          Confirmar firma
        </button>
      </div>
    </div>
  );
}
