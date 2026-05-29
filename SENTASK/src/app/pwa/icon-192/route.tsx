import { ImageResponse } from "next/og";

export const runtime = "edge";

export async function GET() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #1e3a8a, #0f172a)",
          color: "white",
          fontSize: 92,
          fontWeight: 800,
          borderRadius: 40,
          letterSpacing: -4,
        }}
      >
        S
      </div>
    ),
    {
      width: 192,
      height: 192,
    }
  );
}
