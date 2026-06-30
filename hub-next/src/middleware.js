export { auth as middleware } from "@/auth";

// Gate the whole site behind Google sign-in, EXCEPT the auth endpoints
// themselves and static assets (so the sign-in screen can load fonts + logo).
export const config = {
  matcher: ["/((?!api/auth|_next/static|_next/image|favicon.ico|fonts|img).*)"],
};
