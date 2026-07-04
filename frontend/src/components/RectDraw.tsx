import { useRef, useState } from 'react'

export interface Rect { x: number; y: number; w: number; h: number }

/**
 * Rectangle-draw overlay for defining facecam/gameplay regions.
 * Renders on top of a <video>; emits rects in SOURCE pixel coordinates.
 */
export default function RectDraw({
  videoWidth, videoHeight, rect, color, label, onChange,
}: {
  videoWidth: number
  videoHeight: number
  rect: Rect | null
  color: string
  label: string
  onChange: (r: Rect) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [drag, setDrag] = useState<{ x: number; y: number } | null>(null)
  const [preview, setPreview] = useState<Rect | null>(null)

  const toSource = (clientX: number, clientY: number) => {
    const el = ref.current!
    const b = el.getBoundingClientRect()
    const x = ((clientX - b.left) / b.width) * videoWidth
    const y = ((clientY - b.top) / b.height) * videoHeight
    return { x: Math.max(0, Math.min(videoWidth, x)), y: Math.max(0, Math.min(videoHeight, y)) }
  }

  const toScreen = (r: Rect) => {
    return {
      left: `${(r.x / videoWidth) * 100}%`,
      top: `${(r.y / videoHeight) * 100}%`,
      width: `${(r.w / videoWidth) * 100}%`,
      height: `${(r.h / videoHeight) * 100}%`,
    }
  }

  const shown = preview ?? rect

  return (
    <div
      ref={ref}
      className="absolute inset-0 cursor-crosshair"
      onMouseDown={(e) => setDrag(toSource(e.clientX, e.clientY))}
      onMouseMove={(e) => {
        if (!drag) return
        const p = toSource(e.clientX, e.clientY)
        setPreview({
          x: Math.round(Math.min(drag.x, p.x)),
          y: Math.round(Math.min(drag.y, p.y)),
          w: Math.round(Math.abs(p.x - drag.x)),
          h: Math.round(Math.abs(p.y - drag.y)),
        })
      }}
      onMouseUp={() => {
        if (preview && preview.w > 10 && preview.h > 10) onChange(preview)
        setDrag(null)
        setPreview(null)
      }}
    >
      {shown && shown.w > 0 && (
        <div className="absolute border-2" style={{ ...toScreen(shown), borderColor: color }}>
          <span className="absolute -top-6 start-0 rounded px-1 text-xs font-bold"
                style={{ backgroundColor: color, color: '#0f172a' }}>
            {label}
          </span>
        </div>
      )}
    </div>
  )
}
