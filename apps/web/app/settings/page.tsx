import type { Metadata } from "next";
import { ApiKeyInventory } from "@/components/api-key-inventory";
import { ProjectMemberManagement } from "@/components/project-member-management";
export const metadata: Metadata = { title: "Settings" };
export default function Page() {
  return (
    <>
      <ApiKeyInventory />
      <ProjectMemberManagement />
    </>
  );
}
