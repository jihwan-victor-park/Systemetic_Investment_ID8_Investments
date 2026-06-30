import { getCompanyDocx } from "@/lib/firestore";

export const dynamic = "force-dynamic";

export async function GET(_req, { params }) {
  const { slug } = await params;
  const buf = await getCompanyDocx(slug);
  if (!buf) return new Response("Not found", { status: 404 });
  return new Response(buf, {
    headers: {
      "Content-Type":
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "Content-Disposition": `attachment; filename="${slug}.docx"`,
      "Cache-Control": "no-store",
    },
  });
}
