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
          fontSize: 248,
          fontWeight: 800,
          borderRadius: 108,
          letterSpacing: -10,
        }}
      >
        S
      </div>
    ),
    {
      width: 512,
      height: 512,
    }
  );
}
