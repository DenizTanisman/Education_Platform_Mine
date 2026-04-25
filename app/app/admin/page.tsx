import { prisma } from "@/lib/db";

import { IngestTrigger } from "./IngestTrigger";
import { UnitTogglesAndUsers } from "./UnitTogglesAndUsers";

export default async function AdminDashboardPage(): Promise<React.ReactElement> {
  const [units, users] = await Promise.all([
    prisma.unit.findMany({
      orderBy: { order: "asc" },
      select: { id: true, slug: true, order: true, title: true, published: true },
    }),
    prisma.user.findMany({
      orderBy: { createdAt: "desc" },
      select: { id: true, email: true, role: true, createdAt: true },
      take: 100,
    }),
  ]);

  return (
    <div>
      <h1>Admin paneli</h1>
      <IngestTrigger />
      <UnitTogglesAndUsers
        initialUnits={units}
        initialUsers={users.map((u) => ({ ...u, createdAt: u.createdAt.toISOString() }))}
      />
    </div>
  );
}
