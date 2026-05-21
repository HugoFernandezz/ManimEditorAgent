// Project creation now happens via the sidebar modal.
// This route is kept only for deep-link compatibility.
import { redirect } from "next/navigation";
export default function NewPage() {
  redirect("/");
}
